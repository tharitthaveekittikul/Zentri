import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.price import Price

logger = get_logger(__name__)


def _range_start(range_: str) -> datetime:
    days = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    return datetime.now(timezone.utc) - timedelta(days=days.get(range_, 30))


async def _latest_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _prev_day_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=20)
    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id, Price.timestamp < cutoff)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    zero = Decimal("0")
    if not holdings:
        return dict(total_value=zero, total_cost=zero, total_pnl=zero,
                    total_pnl_pct=zero, daily_change=zero, daily_change_pct=zero)

    total_cost = sum(h.quantity * h.avg_cost_price for h in holdings)
    total_value = zero
    yesterday_value = zero

    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if latest:
            total_value += h.quantity * latest.close
        prev = await _prev_day_price(db, h.asset_id)
        if prev:
            yesterday_value += h.quantity * prev.close

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else zero
    daily_change = total_value - yesterday_value
    daily_change_pct = (daily_change / yesterday_value * 100) if yesterday_value else zero

    logger.info("Summary: user=%s total_value=%s total_cost=%s", user_id, total_value, total_cost)
    return dict(total_value=total_value, total_cost=total_cost, total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct, daily_change=daily_change, daily_change_pct=daily_change_pct)


async def get_allocation(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    by_type: dict[str, Decimal] = {}
    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if not latest:
            continue
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        asset_type = asset.asset_type
        by_type[asset_type] = by_type.get(asset_type, Decimal("0")) + h.quantity * latest.close

    total = sum(by_type.values()) or Decimal("1")
    logger.info("Allocation: user=%s types=%s", user_id, list(by_type.keys()))
    return [{"asset_type": k, "value": v, "pct": v / total * 100} for k, v in by_type.items()]


async def get_performance(db: AsyncSession, user_id: uuid.UUID, range_: str) -> dict:
    from datetime import date as date_type
    start = _range_start(range_)
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    date_values: dict[date_type, Decimal] = {}
    for h in holdings:
        prices = list((await db.execute(
            select(Price)
            .where(Price.asset_id == h.asset_id, Price.timestamp >= start)
            .order_by(Price.timestamp.asc())
        )).scalars().all())
        for p in prices:
            d = p.timestamp.date()
            date_values[d] = date_values.get(d, Decimal("0")) + h.quantity * p.close

    portfolio_series = [{"date": d, "value": v} for d, v in sorted(date_values.items())]

    benchmark_asset = (await db.execute(
        select(Asset).where(Asset.symbol == "^GSPC")
    )).scalar_one_or_none()

    benchmark_series: list[dict] = []
    if benchmark_asset:
        b_prices = list((await db.execute(
            select(Price)
            .where(Price.asset_id == benchmark_asset.id, Price.timestamp >= start)
            .order_by(Price.timestamp.asc())
        )).scalars().all())
        benchmark_series = [{"date": p.timestamp.date(), "value": p.close} for p in b_prices]

    def normalize(series: list[dict]) -> list[dict]:
        if not series:
            return []
        base = series[0]["value"]
        if not base:
            return series
        return [{"date": s["date"], "value": s["value"] / base * 100} for s in series]

    logger.info("Performance: user=%s range=%s points=%d", user_id, range_, len(portfolio_series))
    return {"portfolio": normalize(portfolio_series), "benchmark": normalize(benchmark_series)}
