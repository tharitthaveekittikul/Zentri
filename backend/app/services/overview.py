import uuid
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.holding import Holding
from app.models.price import Price
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.services import exchange_rate as fx_service

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


async def get_summary(db: AsyncSession, user_id: uuid.UUID, target_currency: str = "USD") -> dict:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    zero = Decimal("0")
    if not holdings:
        return dict(total_value=zero, total_cost=zero, total_pnl=zero,
                    total_pnl_pct=zero, daily_change=zero, daily_change_pct=zero)

    total_cost = zero
    total_value = zero
    yesterday_value = zero

    for h in holdings:
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        rate = await fx_service.get_rate(db, asset.currency, target_currency)
        multiplier = rate if rate else Decimal("1")

        total_cost += h.quantity * h.avg_cost_price * multiplier

        latest = await _latest_price(db, h.asset_id)
        if latest:
            total_value += h.quantity * latest.close * multiplier
        prev = await _prev_day_price(db, h.asset_id)
        if prev:
            yesterday_value += h.quantity * prev.close * multiplier

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else zero
    daily_change = total_value - yesterday_value
    daily_change_pct = (daily_change / yesterday_value * 100) if yesterday_value else zero

    logger.info("Summary: user=%s target=%s total_value=%s total_cost=%s", user_id, target_currency, total_value, total_cost)
    return dict(total_value=total_value, total_cost=total_cost, total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct, daily_change=daily_change, daily_change_pct=daily_change_pct)


async def get_allocation(db: AsyncSession, user_id: uuid.UUID, target_currency: str = "USD") -> list[dict]:
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
        value_native = h.quantity * latest.close
        rate = await fx_service.get_rate(db, asset.currency, target_currency)
        value_converted = value_native * rate if rate else value_native
        asset_type = asset.asset_type
        by_type[asset_type] = by_type.get(asset_type, Decimal("0")) + value_converted

    # Add cash balances — latest snapshot per cash asset
    cash_assets = list((await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
    )).scalars().all())

    for ca in cash_assets:
        snap_result = await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.desc())
            .limit(1)
        )
        snap = snap_result.scalar_one_or_none()
        if snap:
            balance = Decimal(str(snap.balance))
            rate = await fx_service.get_rate(db, ca.currency, target_currency)
            balance_converted = balance * rate if rate else balance
            by_type["cash"] = by_type.get("cash", Decimal("0")) + balance_converted

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


def _net_worth_range_start(range_: str) -> date | None:
    from datetime import date as date_type
    today = date_type.today()
    ranges = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = ranges.get(range_)
    if days is None:
        return None
    return today - timedelta(days=days)


async def get_net_worth_timeline(
    db: AsyncSession, user_id: uuid.UUID, range_: str
) -> list[dict]:
    stmt = select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == user_id)
    start = _net_worth_range_start(range_)
    if start is not None:
        stmt = stmt.where(NetWorthSnapshot.snapshot_date >= start)
    stmt = stmt.order_by(NetWorthSnapshot.snapshot_date.asc())

    rows = list((await db.execute(stmt)).scalars().all())
    logger.info("net_worth_timeline user=%s range=%s points=%d", user_id, range_, len(rows))
    return [
        {"date": r.snapshot_date, "value_usd": r.total_value_usd, "cost_usd": r.total_cost_usd}
        for r in rows
    ]
