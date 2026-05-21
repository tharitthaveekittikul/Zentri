import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.pipeline_log import PipelineLog
from app.models.pipeline_step import PipelineStep

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


async def create_step(
    db: AsyncSession, pipeline_log_id: uuid.UUID, step_name: str
) -> PipelineStep:
    step = PipelineStep(
        pipeline_log_id=pipeline_log_id,
        step_name=step_name,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    logger.info("pipeline step started step=%s log_id=%s", step_name, pipeline_log_id)
    return step


async def finish_step(
    db: AsyncSession,
    step: PipelineStep,
    *,
    success: bool,
    metadata: dict | None = None,
    error: str | None = None,
) -> PipelineStep:
    step.status = "done" if success else "failed"
    step.finished_at = datetime.now(timezone.utc)
    step.step_metadata = metadata
    step.error_message = error
    await db.commit()
    await db.refresh(step)
    logger.info(
        "pipeline step finished step=%s status=%s", step.step_name, step.status
    )
    return step


async def list_logs(
    db: AsyncSession, limit: int = 50, job_type: str | None = None
) -> list[PipelineLog]:
    q = (
        select(PipelineLog)
        .options(selectinload(PipelineLog.steps))
        .order_by(desc(PipelineLog.started_at))
    )
    if job_type:
        q = q.where(PipelineLog.job_type == job_type)
    result = await db.execute(q.limit(limit))
    return list(result.scalars().all())


async def get_log(db: AsyncSession, log_id: uuid.UUID) -> PipelineLog | None:
    result = await db.execute(
        select(PipelineLog)
        .options(selectinload(PipelineLog.steps))
        .where(PipelineLog.id == log_id)
    )
    return result.scalar_one_or_none()
