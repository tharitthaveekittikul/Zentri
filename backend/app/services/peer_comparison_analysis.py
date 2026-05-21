from __future__ import annotations

import json
import uuid
from decimal import Decimal

import yfinance as yf
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.llm_call_log import LLMCallLog
from app.models.peer_comparison_analysis import PeerComparisonAnalysis
from app.services.exchange_rate import get_current_usd_thb
from app.services.llm_gateway import LLMGateway, LLMGatewayResult, _build_adapter

logger = get_logger(__name__)

PEER_DISCOVERY_SYSTEM = (
    "You are a market analyst. Given a stock ticker and sector, list the 3-5 most direct competitors. "
    "Respond ONLY with a JSON array of uppercase ticker symbols. Example: [\"NVDA\", \"INTC\", \"QCOM\"]"
)


def _parse_json(content: str) -> dict | list | None:
    try:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return None


def _fetch_yfinance_metrics(tickers: list[str]) -> dict[str, dict]:
    result = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            result[t] = {
                "ps_ttm": info.get("priceToSalesTrailing12Months"),
                "ps_forward": info.get("forwardPE"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "gross_margin_pct": round((info.get("grossMargins") or 0) * 100, 1),
                "yoy_revenue_growth_pct": round((info.get("revenueGrowth") or 0) * 100, 1),
            }
        except Exception as e:
            logger.warning("yfinance failed for %s: %s", t, e)
            result[t] = {
                "ps_ttm": None, "ps_forward": None, "ev_ebitda": None,
                "gross_margin_pct": None, "yoy_revenue_growth_pct": None,
            }
    return result


async def _discover_peers(
    symbol: str,
    sector: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[list[str], LLMGatewayResult]:
    from app.models.feature_llm_config import FeatureLLMConfig
    from app.models.provider_config import ProviderConfig
    from app.core.encryption import decrypt

    config_result = await db.execute(
        select(FeatureLLMConfig).where(
            FeatureLLMConfig.feature_key == "peer_comparison",
            FeatureLLMConfig.user_id == user_id,
        )
    )
    config = config_result.scalar_one_or_none()
    if not config:
        raise ValueError("No LLM config for 'peer_comparison'. Configure it in Settings → AI.")

    provider_result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.id == config.provider_config_id)
    )
    provider = provider_result.scalar_one_or_none()
    if not provider or not provider.is_connected:
        raise ValueError("peer_comparison provider not connected")

    api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
    adapter = _build_adapter(provider.provider, api_key, getattr(provider, "host_url", None))

    human = f"Ticker: {symbol}\nSector: {sector}\nList 3-5 direct competitors as a JSON array of tickers."
    response = await adapter.complete(PEER_DISCOVERY_SYSTEM, human, config.model)

    usd_thb = await get_current_usd_thb(db)
    cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

    log = LLMCallLog(
        user_id=user_id,
        feature_key="peer_comparison",
        provider=provider.provider,
        model=config.model,
        prompt_in=f"SYSTEM: {PEER_DISCOVERY_SYSTEM}\n\nHUMAN: {human}",
        response_out=response.content,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
    )
    db.add(log)
    await db.flush()

    peers = _parse_json(response.content)
    if not isinstance(peers, list):
        logger.warning("Peer discovery returned non-list: %s — using defaults", response.content[:100])
        peers = []

    gateway_result = LLMGatewayResult(
        content=response.content, prompt=human,
        tokens_in=response.tokens_in, tokens_out=response.tokens_out,
        cost_usd=float(response.cost_usd), cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
        model=config.model, provider=provider.provider,
    )
    return [t.upper() for t in peers[:5]], gateway_result


def _build_financial_table(symbol: str, metrics: dict[str, dict]) -> str:
    rows = [f"{'Ticker':<8} {'P/S TTM':>10} {'EV/EBITDA':>12} {'Gross Margin':>14} {'Rev Growth YoY':>16}"]
    rows.append("-" * 65)
    all_tickers = [symbol] + [t for t in metrics if t != symbol]
    for t in all_tickers:
        m = metrics.get(t, {})
        rows.append(
            f"{t:<8} "
            f"{str(m.get('ps_ttm') or 'N/A'):>10} "
            f"{str(m.get('ev_ebitda') or 'N/A'):>12} "
            f"{str(m.get('gross_margin_pct') or 'N/A') + '%':>14} "
            f"{str(m.get('yoy_revenue_growth_pct') or 'N/A') + '%':>16}"
        )
    return "\n".join(rows)


async def run_peer_comparison(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> PeerComparisonAnalysis:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    sector = asset.metadata_.get("sector", "Unknown")

    peers, _ = await _discover_peers(symbol.upper(), sector, user_id, db)
    all_tickers = [symbol.upper()] + peers
    metrics = _fetch_yfinance_metrics(all_tickers)
    financial_table = _build_financial_table(symbol.upper(), metrics)

    variables = {
        "symbol": symbol.upper(),
        "sector": sector,
        "financial_table": financial_table,
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("peer_comparison", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed or not isinstance(parsed, dict):
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    analysis = PeerComparisonAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        sector_label=parsed.get("sector_label", sector),
        ranked=parsed.get("ranked", []),
        methodology_note=parsed.get("methodology_note", "Value/Growth Score = P/S TTM / YoY Revenue Growth %"),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("PeerComparisonAnalysis saved: user=%s symbol=%s peers=%s", user_id, symbol, peers)
    return analysis


async def get_latest_peer_comparison(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> PeerComparisonAnalysis | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(PeerComparisonAnalysis)
        .where(PeerComparisonAnalysis.asset_id == asset.id, PeerComparisonAnalysis.user_id == user_id)
        .order_by(desc(PeerComparisonAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
