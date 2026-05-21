from __future__ import annotations

import json
import uuid
from decimal import Decimal

import yfinance as yf
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.bear_case_analysis import BearCaseAnalysis
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)


def _parse_json(content: str) -> dict | None:
    try:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return None


def _fetch_yfinance_vars(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        gross_margin = info.get("grossMargins", 0) or 0
        op_margin = info.get("operatingMargins", 0) or 0
        rev_growth = info.get("revenueGrowth", 0) or 0
        debt_equity = info.get("debtToEquity", 0) or 0
        short_pct = info.get("shortPercentOfFloat", 0) or 0

        try:
            qf = ticker.quarterly_financials
            gp_row = qf.loc["Gross Profit"] if "Gross Profit" in qf.index else None
            rev_row = qf.loc["Total Revenue"] if "Total Revenue" in qf.index else None
            if gp_row is not None and rev_row is not None:
                q_margins = [
                    f"{float(gp / rv) * 100:.1f}%" if rv else "N/A"
                    for gp, rv in zip(gp_row.iloc[:4], rev_row.iloc[:4])
                ]
                gross_margins_4q = ", ".join(q_margins)
            else:
                gross_margins_4q = f"{gross_margin * 100:.1f}% (TTM only)"
        except Exception:
            gross_margins_4q = f"{gross_margin * 100:.1f}% (TTM only)"

        return {
            "gross_margins_4q": gross_margins_4q,
            "revenue_growth_yoy": f"{rev_growth * 100:.1f}",
            "operating_margin": f"{op_margin * 100:.1f}",
            "debt_equity": f"{debt_equity:.1f}",
            "short_interest_pct": f"{short_pct * 100:.1f}",
        }
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s — using N/A defaults", symbol, e)
        return {
            "gross_margins_4q": "N/A",
            "revenue_growth_yoy": "N/A",
            "operating_margin": "N/A",
            "debt_equity": "N/A",
            "short_interest_pct": "N/A",
        }


async def run_bear_case(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> BearCaseAnalysis:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    yf_vars = _fetch_yfinance_vars(symbol.upper())

    variables = {
        "symbol": symbol.upper(),
        "company_name": asset.name,
        "sector": asset.metadata_.get("sector", "Unknown"),
        **yf_vars,
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("bear_case", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed:
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    analysis = BearCaseAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        red_flags=parsed.get("red_flags", []),
        summary=parsed.get("summary", ""),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("BearCaseAnalysis saved: user=%s symbol=%s", user_id, symbol)
    return analysis


async def get_latest_bear_case(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> BearCaseAnalysis | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(BearCaseAnalysis)
        .where(BearCaseAnalysis.asset_id == asset.id, BearCaseAnalysis.user_id == user_id)
        .order_by(desc(BearCaseAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
