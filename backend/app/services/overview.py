import uuid
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.benchmark import Benchmark, BenchmarkPrice
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
            total_value += balance_converted
            total_cost += balance_converted
            yesterday_value += balance_converted

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
    from app.models.transaction import Transaction

    start = _range_start(range_)
    start_date = start.date()

    # Load all transactions (all-time) so qty replay is accurate for pre-range holdings
    txs_result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.type.in_(["buy", "sell", "reward"]),
        )
        .order_by(Transaction.executed_at.asc())
    )
    transactions = list(txs_result.scalars().all())

    if not transactions:
        return {"portfolio": [], "benchmark": []}

    asset_ids = list({t.asset_id for t in transactions})

    # Build FX rate map: asset_id → conversion rate to USD (using today's rate)
    rate_map: dict[uuid.UUID, Decimal] = {}
    for asset_id in asset_ids:
        asset = (await db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
        if asset:
            rate = await fx_service.get_rate(db, asset.currency, "USD")
            rate_map[asset_id] = rate if rate else Decimal("1")
        else:
            rate_map[asset_id] = Decimal("1")

    # Batch-fetch prices for all transaction assets in the range
    asset_prices: dict[uuid.UUID, list[tuple[date_type, Decimal]]] = {}
    for asset_id in asset_ids:
        prices_result = await db.execute(
            select(Price.timestamp, Price.close)
            .where(Price.asset_id == asset_id, Price.timestamp >= start)
            .order_by(Price.timestamp.asc())
        )
        asset_prices[asset_id] = [(row[0].date(), row[1]) for row in prices_result.all()]

    all_dates = sorted({d for dates_list in asset_prices.values() for d, _ in dates_list})
    if not all_dates:
        return {"portfolio": [], "benchmark": []}

    # Pre-group in-range transactions by date for O(1) lookup in the main loop.
    # Rewards are excluded — they are investment returns, not external capital.
    txs_by_date: dict[date_type, list] = {}
    for tx in transactions:
        if tx.type == "reward":
            continue
        d = tx.executed_at.date()
        if d >= start_date:
            txs_by_date.setdefault(d, []).append(tx)

    def get_price(asset_id: uuid.UUID, target: date_type) -> Decimal | None:
        result = None
        for d, close in asset_prices.get(asset_id, []):
            if d <= target:
                result = close
            else:
                break
        return result

    # TWR via Dietz daily chain-linking: return = V_d / (V_{d-1} + CF_d) - 1
    # CF_d is only counted for assets that have price data ON that date —
    # assets without prices on a given date (Thai stocks with partial history,
    # Thai funds) are excluded from both portfolio_value AND CF, keeping the
    # calculation self-consistent and preventing phantom losses.
    twr_index = Decimal("100")
    prev_value: Decimal | None = None
    twr_points: list[dict] = []

    for current_date in all_dates:
        # Replay transactions up to current_date
        qty_map: dict[uuid.UUID, Decimal] = {}
        for tx in transactions:
            if tx.executed_at.date() > current_date:
                break
            if tx.type in ("buy", "reward"):
                qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) + tx.quantity
            elif tx.type == "sell":
                qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) - tx.quantity

        portfolio_value = Decimal("0")
        for asset_id, qty in qty_map.items():
            if qty <= 0:
                continue
            price = get_price(asset_id, current_date)
            if price:
                portfolio_value += qty * price * rate_map.get(asset_id, Decimal("1"))

        if portfolio_value > 0:
            if prev_value is not None and prev_value > 0:
                # CF only for assets with price data on current_date, converted to USD
                cf = Decimal("0")
                for tx in txs_by_date.get(current_date, []):
                    if get_price(tx.asset_id, current_date) is not None:
                        flow = tx.quantity * tx.price * rate_map.get(tx.asset_id, Decimal("1"))
                        if tx.type == "sell":
                            flow = -flow
                        cf += flow
                base = prev_value + cf
                if base > 0:
                    twr_index = twr_index * (portfolio_value / base)
            twr_points.append({"date": current_date, "value": twr_index})
            prev_value = portfolio_value

    # Benchmark (S&P500)
    benchmark_record = (await db.execute(
        select(Benchmark).where(Benchmark.symbol == "^GSPC")
    )).scalar_one_or_none()

    benchmark_series: list[dict] = []
    if benchmark_record:
        b_prices = list((await db.execute(
            select(BenchmarkPrice)
            .where(BenchmarkPrice.benchmark_id == benchmark_record.id, BenchmarkPrice.timestamp >= start)
            .order_by(BenchmarkPrice.timestamp.asc())
        )).scalars().all())
        benchmark_series = [{"date": p.timestamp.date(), "value": p.close} for p in b_prices]

    # Align both to the same start date before renormalizing to 100
    if twr_points and benchmark_series:
        common_start = max(twr_points[0]["date"], benchmark_series[0]["date"])
        twr_points = [s for s in twr_points if s["date"] >= common_start]
        benchmark_series = [s for s in benchmark_series if s["date"] >= common_start]
        if twr_points:
            twr_base = twr_points[0]["value"]
            twr_points = [{"date": s["date"], "value": float(s["value"] / twr_base * Decimal("100"))} for s in twr_points]

    def normalize_bm(series: list[dict]) -> list[dict]:
        if not series:
            return []
        base = series[0]["value"]
        if not base:
            return series
        return [{"date": s["date"], "value": float(s["value"] / base * 100)} for s in series]

    logger.info("Performance TWR: user=%s range=%s points=%d", user_id, range_, len(twr_points))
    return {"portfolio": twr_points, "benchmark": normalize_bm(benchmark_series)}


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
