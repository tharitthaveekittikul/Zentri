import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.platform import Platform

logger = get_logger(__name__)


async def create_platform(
    db: AsyncSession, user_id: uuid.UUID, name: str, asset_types_supported: list[str], notes: str | None
) -> Platform:
    platform = Platform(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        asset_types_supported=asset_types_supported,
        notes=notes,
    )
    db.add(platform)
    await db.commit()
    await db.refresh(platform)
    logger.info("Platform created: name=%s user=%s id=%s", name, user_id, platform.id)
    return platform


async def list_platforms(db: AsyncSession, user_id: uuid.UUID) -> list[Platform]:
    result = await db.execute(select(Platform).where(Platform.user_id == user_id))
    return list(result.scalars().all())


async def get_platform(db: AsyncSession, user_id: uuid.UUID, platform_id: uuid.UUID) -> Platform | None:
    result = await db.execute(
        select(Platform).where(Platform.id == platform_id, Platform.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_platform(
    db: AsyncSession, platform: Platform, name: str, asset_types_supported: list[str], notes: str | None
) -> Platform:
    platform.name = name
    platform.asset_types_supported = asset_types_supported
    platform.notes = notes
    await db.commit()
    await db.refresh(platform)
    logger.info("Platform updated: id=%s name=%s", platform.id, name)
    return platform


async def delete_platform(db: AsyncSession, platform: Platform) -> None:
    logger.info("Platform deleted: id=%s name=%s", platform.id, platform.name)
    await db.delete(platform)
    await db.commit()
