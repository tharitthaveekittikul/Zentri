from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.holding import Holding
from app.models.overview_analysis import OverviewAnalysis
from app.models.price import Price
from app.models.user import User
from app.services import exchange_rate as fx_service
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)

COOLDOWN_MINUTES = 30


async def _latest_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    result = await db.execute(
        select(Price).where(Price.asset_id == asset_id).order_by(desc(Price.timestamp)).limit(1)
    )
    return result.scalar_one_or_none()


async def _build_variables(
    db: AsyncSession, user_id: uuid.UUID, currency: str
) -> dict:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )

    holding_rows: list[str] = []
    total_value = Decimal("0")
    total_cost = Decimal("0")

    for h in holdings:
        asset = (await db.execute(select(Asset).where(Asset.id == h.asset_id))).scalar_one_or_none()
        if not asset:
            continue
        rate = await fx_service.get_rate(db, asset.currency, currency) or Decimal("1")
        latest = await _latest_price(db, h.asset_id)
        current_price = latest.close if latest else h.avg_cost_price
        value = h.quantity * current_price * rate
        cost = h.quantity * h.avg_cost_price * rate
        total_value += value
        total_cost += cost
        holding_rows.append(
            f"{asset.symbol} | {h.quantity:.4f} | {float(h.avg_cost_price):.2f} "
            f"| {float(current_price):.2f} | {float(value):.0f} {currency}"
        )

    cash_rows: list[str] = []
    cash_assets = list(
        (await db.execute(
            select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
        )).scalars().all()
    )
    for ca in cash_assets:
        snap = (
            await db.execute(
                select(CashBalance)
                .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
                .order_by(CashBalance.snapshot_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snap:
            balance = Decimal(str(snap.balance))
            rate = await fx_service.get_rate(db, ca.currency, currency) or Decimal("1")
            converted = balance * rate
            total_value += converted
            total_cost += converted
            cash_rows.append(f"{ca.currency} | {float(balance):.2f} | {float(converted):.0f} {currency}")

    pnl_pct = float((total_value - total_cost) / total_cost * 100) if total_cost else 0.0

    holdings_table = "\n".join(holding_rows) if holding_rows else "No holdings"
    cash_table = "\n".join(cash_rows) if cash_rows else "No cash balances"

    return {
        "holdings_table": holdings_table,
        "cash_table": cash_table,
        "total_value": f"{float(total_value):.0f}",
        "num_holdings": str(len(holding_rows)),
        "total_pnl_pct": f"{pnl_pct:.1f}",
    }


def _parse_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if not isinstance(data.get("score"), int):
            return None
        if data.get("grade") not in ("A", "B", "C", "D", "F"):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def run_overview_analysis(
    db: AsyncSession, user_id: uuid.UUID
) -> OverviewAnalysis:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    currency = getattr(user, "currency_primary", None) or "USD" if user else "USD"

    variables = await _build_variables(db, user_id, currency)
    logger.info("Running overview analysis: user=%s currency=%s", user_id, currency)

    gateway = LLMGateway(db)
    result = await gateway.complete("overview_analysis", user_id, variables)

    parsed = _parse_response(result.content)
    if not parsed:
        raise ValueError(f"LLM returned invalid overview analysis JSON: {result.content[:200]}")

    analysis = OverviewAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        score=int(parsed.get("score", 50)),
        grade=parsed.get("grade", "C"),
        health=parsed.get("health", "Moderate"),
        portfolio_adherence_pct=parsed.get("portfolio_adherence_pct"),
        insights=parsed.get("insights", []),
        top_action=parsed.get("top_action", ""),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
        cost_thb=Decimal(str(result.cost_thb)),
        exchange_rate=Decimal(str(result.exchange_rate)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("Overview analysis saved: user=%s score=%d grade=%s", user_id, analysis.score, analysis.grade)
    return analysis


async def get_latest_overview_analysis(
    db: AsyncSession, user_id: uuid.UUID
) -> OverviewAnalysis | None:
    result = await db.execute(
        select(OverviewAnalysis)
        .where(OverviewAnalysis.user_id == user_id)
        .order_by(desc(OverviewAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def is_cooldown_active(analysis: OverviewAnalysis | None) -> bool:
    if not analysis:
        return False
    age = datetime.now(timezone.utc) - analysis.created_at
    return age < timedelta(minutes=COOLDOWN_MINUTES)
