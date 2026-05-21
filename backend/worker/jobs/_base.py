from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset

logger = get_logger(__name__)


async def handle_job_error(
    symbol: str,
    user_id: uuid.UUID,
    error: Exception,
    make_error_record: Callable[[uuid.UUID], object],
    db: AsyncSession,
) -> None:
    try:
        await db.rollback()
        result = await db.execute(
            select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
        )
        asset = result.scalar_one_or_none()
        if asset:
            db.add(make_error_record(asset.id))
            await db.commit()
    except Exception:
        logger.exception("handle_job_error: failed to save error record symbol=%s", symbol)
