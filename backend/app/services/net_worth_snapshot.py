import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.holding import Holding
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.models.price import Price
from app.models.transaction import Transaction
from app.services import exchange_rate as fx_service

logger = get_logger(__name__)


def compute_snapshot(
    holdings: list, price_map: dict[uuid.UUID, Decimal], rate_map: dict[uuid.UUID, Decimal]
) -> dict | None:
    total_value = Decimal("0")
    total_cost = Decimal("0")
    any_priced = False

    for h in holdings:
        price = price_map.get(h.asset_id)
        if price is None:
            continue
        rate = rate_map.get(h.asset_id, Decimal("1"))
        total_value += h.quantity * price * rate
        total_cost += h.quantity * h.avg_cost_price * rate
        any_priced = True

    if not any_priced:
        return None
    return {"total_value_usd": total_value, "total_cost_usd": total_cost}


async def _build_rate_map(db: AsyncSession, asset_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    rate_map: dict[uuid.UUID, Decimal] = {}
    for asset_id in asset_ids:
        asset = (await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )).scalar_one_or_none()
        if asset:
            rate = await fx_service.get_rate(db, asset.currency, "USD")
            rate_map[asset_id] = rate if rate else Decimal("1")
        else:
            rate_map[asset_id] = Decimal("1")
    return rate_map


def _replay_transactions(transactions: list, up_to_date: date) -> dict[uuid.UUID, Decimal]:
    """Compute quantity held per asset as of up_to_date by replaying transactions in order."""
    qty_map: dict[uuid.UUID, Decimal] = {}
    for tx in transactions:
        if tx.executed_at.date() > up_to_date:
            break
        if tx.type in ("buy", "reward"):
            qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) + tx.quantity
        elif tx.type == "sell":
            qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) - tx.quantity
    return qty_map


async def _get_price_on_date(
    db: AsyncSession, asset_id: uuid.UUID, target_date: date
) -> Decimal | None:
    cutoff = datetime(
        target_date.year, target_date.month, target_date.day,
        23, 59, 59, tzinfo=timezone.utc
    )
    result = await db.execute(
        select(Price.close)
        .where(Price.asset_id == asset_id, Price.timestamp <= cutoff)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_cash_total_on_date(
    db: AsyncSession, user_id: uuid.UUID, target_date: date
) -> Decimal:
    """Return total cash value in USD as of target_date, using latest CashBalance per asset."""
    cash_assets = list((await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
    )).scalars().all())

    total = Decimal("0")
    for ca in cash_assets:
        snap = (await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id,
                   CashBalance.snapshot_date <= target_date)
            .order_by(CashBalance.snapshot_date.desc())
            .limit(1)
        )).scalar_one_or_none()
        if snap:
            balance = Decimal(str(snap.balance))
            rate = await fx_service.get_rate(db, ca.currency, "USD")
            total += balance * (rate if rate else Decimal("1"))
    return total


async def take_snapshot(
    db: AsyncSession, user_id: uuid.UUID, snapshot_date: date
) -> NetWorthSnapshot | None:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    if not holdings:
        return None

    rate_map = await _build_rate_map(db, [h.asset_id for h in holdings])

    price_map: dict[uuid.UUID, Decimal] = {}
    for h in holdings:
        price = await _get_price_on_date(db, h.asset_id, snapshot_date)
        if price is not None:
            price_map[h.asset_id] = price

    computed = compute_snapshot(holdings, price_map, rate_map)
    total_value = computed["total_value_usd"] if computed else Decimal("0")
    total_cost = computed["total_cost_usd"] if computed else Decimal("0")

    cash_total = await _get_cash_total_on_date(db, user_id, snapshot_date)
    total_value += cash_total
    total_cost += cash_total

    if total_value == 0:
        logger.info("snapshot skipped user=%s date=%s (no data)", user_id, snapshot_date)
        return None

    snapshot = NetWorthSnapshot(
        user_id=user_id,
        snapshot_date=snapshot_date,
        total_value_usd=total_value,
        total_cost_usd=total_cost,
    )
    db.add(snapshot)
    try:
        await db.commit()
        await db.refresh(snapshot)
        logger.info("snapshot saved user=%s date=%s value=%s", user_id, snapshot_date, computed["total_value_usd"])
        return snapshot
    except IntegrityError:
        await db.rollback()
        logger.debug("snapshot already exists user=%s date=%s (skipped)", user_id, snapshot_date)
        return None


async def backfill_snapshots(db: AsyncSession, user_id: uuid.UUID) -> int:
    # Load all buy/sell/reward transactions sorted by date — fetched once into memory
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
        return 0

    asset_ids = list({t.asset_id for t in transactions})

    # FX rates (today's rates — acceptable approximation for trend chart)
    rate_map = await _build_rate_map(db, asset_ids)

    # avg_cost_price from current holdings (approximation for cost line)
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )
    avg_cost_map: dict[uuid.UUID, Decimal] = {
        h.asset_id: h.avg_cost_price
        for h in holdings_result.scalars().all()
    }

    earliest_date = transactions[0].executed_at.date()
    yesterday = date.today() - timedelta(days=1)

    existing_result = await db.execute(
        select(NetWorthSnapshot.snapshot_date).where(NetWorthSnapshot.user_id == user_id)
    )
    existing_dates = {row[0] for row in existing_result.all()}

    # Pre-fetch cash assets and all their balance history (sorted asc for linear scan)
    cash_assets = list((await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
    )).scalars().all())

    cash_rate_map: dict[uuid.UUID, Decimal] = {}
    for ca in cash_assets:
        rate = await fx_service.get_rate(db, ca.currency, "USD")
        cash_rate_map[ca.id] = rate if rate else Decimal("1")

    cash_balance_history: dict[uuid.UUID, list[tuple[date, Decimal]]] = {}
    for ca in cash_assets:
        cb_result = await db.execute(
            select(CashBalance.snapshot_date, CashBalance.balance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.asc())
        )
        cash_balance_history[ca.id] = [(row[0], Decimal(str(row[1]))) for row in cb_result.all()]

    def get_cash_for_date(target_date: date) -> Decimal:
        total = Decimal("0")
        for ca in cash_assets:
            rate = cash_rate_map.get(ca.id, Decimal("1"))
            latest: Decimal | None = None
            for snap_date, balance in cash_balance_history.get(ca.id, []):
                if snap_date <= target_date:
                    latest = balance
                else:
                    break
            if latest is not None:
                total += latest * rate
        return total

    # Batch-fetch all historical prices for all transaction assets
    start_dt = datetime(earliest_date.year, earliest_date.month, earliest_date.day, 0, 0, 0, tzinfo=timezone.utc)
    cutoff_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=timezone.utc)

    asset_prices: dict[uuid.UUID, list[tuple[datetime, Decimal]]] = {}
    for asset_id in asset_ids:
        prices_result = await db.execute(
            select(Price.timestamp, Price.close)
            .where(
                Price.asset_id == asset_id,
                Price.timestamp >= start_dt,
                Price.timestamp <= cutoff_dt,
            )
            .order_by(Price.timestamp.asc())
        )
        asset_prices[asset_id] = [(row[0], row[1]) for row in prices_result.all()]

    def get_price_for_date(asset_id: uuid.UUID, target_date: date) -> Decimal | None:
        prices = asset_prices.get(asset_id, [])
        cutoff = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        result = None
        for ts, close in prices:
            if ts <= cutoff:
                result = close
            else:
                break
        return result

    count = 0
    current = earliest_date
    while current <= yesterday:
        if current not in existing_dates:
            qty_map = _replay_transactions(transactions, current)

            total_value = Decimal("0")
            total_cost = Decimal("0")
            any_priced = False

            for asset_id, qty in qty_map.items():
                if qty <= 0:
                    continue
                price = get_price_for_date(asset_id, current)
                if price is None:
                    continue
                rate = rate_map.get(asset_id, Decimal("1"))
                avg_cost = avg_cost_map.get(asset_id, Decimal("0"))
                total_value += qty * price * rate
                total_cost += qty * avg_cost * rate
                any_priced = True

            cash_total = get_cash_for_date(current)
            total_value += cash_total
            total_cost += cash_total
            any_priced = any_priced or cash_total > 0

            if any_priced:
                snapshot = NetWorthSnapshot(
                    user_id=user_id,
                    snapshot_date=current,
                    total_value_usd=total_value,
                    total_cost_usd=total_cost,
                )
                db.add(snapshot)
                try:
                    await db.commit()
                    await db.refresh(snapshot)
                    count += 1
                except IntegrityError:
                    await db.rollback()

        current += timedelta(days=1)

    logger.info("backfill complete user=%s snapshots=%d", user_id, count)
    return count
