import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset


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
