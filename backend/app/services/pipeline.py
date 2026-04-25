import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.pipeline_log import PipelineLog

logger = get_logger(__name__)


async def create_log(db: AsyncSession, job_type: str) -> PipelineLog:
    log = PipelineLog(
        job_type=job_type,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.info("pipeline job started job_type=%s id=%s", job_type, log.id)
    return log


async def finish_log(
    db: AsyncSession,
    log: PipelineLog,
    *,
    success: bool,
    error_message: str | None = None,
) -> PipelineLog:
    log.status = "done" if success else "failed"
    log.finished_at = datetime.now(timezone.utc)
    log.error_message = error_message
    await db.commit()
    await db.refresh(log)
    logger.info(
        "pipeline job finished job_type=%s status=%s id=%s",
        log.job_type, log.status, log.id,
    )
    return log


async def list_logs(db: AsyncSession, limit: int = 50) -> list[PipelineLog]:
    result = await db.execute(
        select(PipelineLog).order_by(desc(PipelineLog.started_at)).limit(limit)
    )
    return list(result.scalars().all())


async def get_log(db: AsyncSession, log_id: uuid.UUID) -> PipelineLog | None:
    result = await db.execute(
        select(PipelineLog).where(PipelineLog.id == log_id)
    )
    return result.scalar_one_or_none()
