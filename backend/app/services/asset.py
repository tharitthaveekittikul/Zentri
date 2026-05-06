import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset

logger = get_logger(__name__)


async def create_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    name: str,
    currency: str = "USD",
    metadata_: dict[str, Any] | None = None,
) -> Asset:
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user_id,
        symbol=symbol.upper(),
        asset_type=asset_type,
        name=name,
        currency=currency,
        metadata_=metadata_ or {},
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    logger.info("Asset created: symbol=%s type=%s user=%s id=%s", symbol.upper(), asset_type, user_id, asset.id)
    return asset


async def search_assets(db: AsyncSession, user_id: uuid.UUID, query: str) -> list[Asset]:
    result = await db.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.symbol.ilike(f"%{query.upper()}%") | Asset.name.ilike(f"%{query}%"),
        ).limit(20)
    )
    return list(result.scalars().all())


async def get_asset(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> Asset | None:
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_assets(db: AsyncSession, user_id: uuid.UUID) -> list[Asset]:
    result = await db.execute(select(Asset).where(Asset.user_id == user_id))
    return list(result.scalars().all())


async def update_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    updates: dict[str, Any],
) -> Asset | None:
    asset = await get_asset(db, user_id, asset_id)
    if asset is None:
        return None
    for field, value in updates.items():
        setattr(asset, field, value)
    await db.commit()
    await db.refresh(asset)
    logger.info("Asset updated: id=%s user=%s fields=%s", asset_id, user_id, list(updates.keys()))
    return asset


async def delete_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> bool:
    from sqlalchemy import delete as sql_delete
    from app.models.cash_balance import CashBalance

    asset = await get_asset(db, user_id, asset_id)
    if asset is None:
        return False
    await db.execute(sql_delete(CashBalance).where(CashBalance.asset_id == asset_id))
    await db.delete(asset)
    await db.commit()
    logger.info("Asset deleted: id=%s user=%s", asset_id, user_id)
    return True
