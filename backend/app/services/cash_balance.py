import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.cash_balance import CashBalance

logger = get_logger(__name__)


async def create_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    balance: float,
    snapshot_date: date,
    notes: str | None = None,
) -> CashBalance:
    snap = CashBalance(
        user_id=user_id,
        asset_id=asset_id,
        balance=balance,
        snapshot_date=snapshot_date,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    logger.info("Cash snapshot created: asset=%s balance=%s date=%s", asset_id, balance, snapshot_date)
    return snap


async def get_latest(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> CashBalance | None:
    result = await db.execute(
        select(CashBalance)
        .where(CashBalance.asset_id == asset_id, CashBalance.user_id == user_id)
        .order_by(CashBalance.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_history(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> list[CashBalance]:
    result = await db.execute(
        select(CashBalance)
        .where(CashBalance.asset_id == asset_id, CashBalance.user_id == user_id)
        .order_by(CashBalance.snapshot_date.asc())
    )
    return list(result.scalars().all())
