import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.holding import Holding
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.models.price import Price

logger = get_logger(__name__)


def compute_snapshot(
    holdings: list, price_map: dict[uuid.UUID, Decimal]
) -> dict | None:
    total_value = Decimal("0")
    total_cost = Decimal("0")
    any_priced = False

    for h in holdings:
        price = price_map.get(h.asset_id)
        if price is None:
            continue
        total_value += h.quantity * price
        total_cost += h.quantity * h.avg_cost_price
        any_priced = True

    if not any_priced:
        return None
    return {"total_value_usd": total_value, "total_cost_usd": total_cost}


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


async def take_snapshot(
    db: AsyncSession, user_id: uuid.UUID, snapshot_date: date
) -> NetWorthSnapshot | None:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    if not holdings:
        return None

    price_map: dict[uuid.UUID, Decimal] = {}
    for h in holdings:
        price = await _get_price_on_date(db, h.asset_id, snapshot_date)
        if price is not None:
            price_map[h.asset_id] = price

    computed = compute_snapshot(holdings, price_map)
    if computed is None:
        logger.info("snapshot skipped user=%s date=%s (no prices)", user_id, snapshot_date)
        return None

    snapshot = NetWorthSnapshot(
        user_id=user_id,
        snapshot_date=snapshot_date,
        total_value_usd=computed["total_value_usd"],
        total_cost_usd=computed["total_cost_usd"],
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
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    if not holdings:
        return 0

    earliest_result = await db.execute(
        select(func.min(Price.timestamp))
        .where(Price.asset_id.in_([h.asset_id for h in holdings]))
    )
    earliest_ts = earliest_result.scalar_one_or_none()
    if earliest_ts is None:
        return 0

    earliest_date = earliest_ts.date()
    yesterday = date.today() - timedelta(days=1)

    existing_result = await db.execute(
        select(NetWorthSnapshot.snapshot_date).where(NetWorthSnapshot.user_id == user_id)
    )
    existing_dates = {row[0] for row in existing_result.all()}

    # Batch-fetch all prices per asset in one query each (N_assets queries total)
    # Build: {asset_id: [(timestamp, close), ...]} sorted ascending
    asset_prices: dict[uuid.UUID, list[tuple[datetime, Decimal]]] = {}
    cutoff_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=timezone.utc)
    start_dt = datetime(earliest_date.year, earliest_date.month, earliest_date.day, 0, 0, 0, tzinfo=timezone.utc)

    for h in holdings:
        prices_result = await db.execute(
            select(Price.timestamp, Price.close)
            .where(Price.asset_id == h.asset_id, Price.timestamp >= start_dt, Price.timestamp <= cutoff_dt)
            .order_by(Price.timestamp.asc())
        )
        asset_prices[h.asset_id] = [(row[0], row[1]) for row in prices_result.all()]

    def get_price_for_date(asset_id: uuid.UUID, target_date: date) -> Decimal | None:
        """Binary-search the pre-fetched list for the last price on or before target_date."""
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
            price_map: dict[uuid.UUID, Decimal] = {}
            for h in holdings:
                price = get_price_for_date(h.asset_id, current)
                if price is not None:
                    price_map[h.asset_id] = price

            computed = compute_snapshot(holdings, price_map)
            if computed is not None:
                snapshot = NetWorthSnapshot(
                    user_id=user_id,
                    snapshot_date=current,
                    total_value_usd=computed["total_value_usd"],
                    total_cost_usd=computed["total_cost_usd"],
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
