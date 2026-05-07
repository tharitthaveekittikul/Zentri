import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.pipeline_log import PipelineLog
from app.models.price_schedule_config import PriceScheduleConfig
from app.models.user import User
from app.schemas.price_schedule_config import ScheduleConfigIn

logger = get_logger(__name__)

VALID_JOB_KEYS = frozenset(
    {"us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"}
)

JOB_KEY_TO_LOG_TYPE: dict[str, str] = {
    "us_stock": "price_fetch_us",
    "crypto": "price_fetch_crypto",
    "gold": "price_fetch_gold",
    "thai_stock": "price_fetch_thai_stock",
    "thai_fund": "price_fetch_th_fund",
    "benchmark": "price_fetch_benchmark",
}

DEFAULT_CONFIGS: dict[str, dict] = {
    "us_stock":   {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 19, "run_at_minute": 0, "interval_minutes": 15},
    "thai_stock": {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 13, "run_at_minute": 0, "interval_minutes": None},
    "thai_fund":  {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 13, "run_at_minute": 0, "interval_minutes": None},
    "crypto":     {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0, "interval_minutes": 15},
    "gold":       {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0, "interval_minutes": 15},
    "benchmark":  {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0, "interval_minutes": None},
}


async def get_all_configs(
    db: AsyncSession, user_id: uuid.UUID
) -> list[PriceScheduleConfig]:
    """Return all 6 schedule configs for user, seeding defaults for any missing rows."""
    result = await db.execute(
        select(PriceScheduleConfig).where(PriceScheduleConfig.user_id == user_id)
    )
    existing = {c.job_key: c for c in result.scalars().all()}

    configs: list[PriceScheduleConfig] = []
    for job_key, defaults in DEFAULT_CONFIGS.items():
        if job_key not in existing:
            config = PriceScheduleConfig(user_id=user_id, job_key=job_key, **defaults)
            db.add(config)
            configs.append(config)
        else:
            configs.append(existing[job_key])
    await db.flush()
    return configs


async def upsert_configs(
    db: AsyncSession, user_id: uuid.UUID, updates: list[ScheduleConfigIn]
) -> list[PriceScheduleConfig]:
    """Bulk upsert schedule configs. Ignores unknown job_keys."""
    result = await db.execute(
        select(PriceScheduleConfig).where(PriceScheduleConfig.user_id == user_id)
    )
    existing = {c.job_key: c for c in result.scalars().all()}

    configs: list[PriceScheduleConfig] = []
    now = datetime.now(timezone.utc)
    for item in updates:
        if item.job_key not in VALID_JOB_KEYS:
            continue
        if item.job_key in existing:
            config = existing[item.job_key]
            config.enabled = item.enabled
            config.days = item.days
            config.run_at_hour = item.run_at_hour
            config.run_at_minute = item.run_at_minute
            config.interval_minutes = item.interval_minutes
            config.updated_at = now
        else:
            config = PriceScheduleConfig(
                user_id=user_id,
                job_key=item.job_key,
                enabled=item.enabled,
                days=item.days,
                run_at_hour=item.run_at_hour,
                run_at_minute=item.run_at_minute,
                interval_minutes=item.interval_minutes,
            )
            db.add(config)
        configs.append(config)
    await db.flush()
    return configs


async def should_run_job(db: AsyncSession, job_key: str) -> bool:
    """Check if job should run based on primary user's schedule config and timezone.

    interval_minutes=None  -> once_daily: fire only when hour == run_at_hour
    interval_minutes=N     -> interval: fire when hour >= run_at_hour AND
                             at least N minutes have elapsed since last successful run
    """
    result = await db.execute(select(User).order_by(User.created_at).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        return True

    configs = await get_all_configs(db, user.id)
    config = next((c for c in configs if c.job_key == job_key), None)
    if not config:
        return True

    if not config.enabled:
        logger.debug("job %s skipped: disabled", job_key)
        return False

    tz = ZoneInfo(user.schedule_timezone or "Asia/Bangkok")
    now_tz = datetime.now(tz)

    if now_tz.weekday() not in config.days:
        logger.debug("job %s skipped: weekday %d not in %s", job_key, now_tz.weekday(), config.days)
        return False

    if config.interval_minutes is None:
        return now_tz.hour == config.run_at_hour

    # Interval job: must be past start hour
    if now_tz.hour < config.run_at_hour:
        return False

    # Check time since last successful run
    log_type = JOB_KEY_TO_LOG_TYPE.get(job_key)
    if log_type:
        last_result = await db.execute(
            select(PipelineLog)
            .where(PipelineLog.job_type == log_type, PipelineLog.status == "done")
            .order_by(PipelineLog.finished_at.desc())
            .limit(1)
        )
        last_log = last_result.scalar_one_or_none()
        if last_log and last_log.finished_at:
            elapsed_min = (datetime.now(timezone.utc) - last_log.finished_at).total_seconds() / 60
            if elapsed_min < config.interval_minutes:
                logger.debug("job %s skipped: only %.1f min since last run (interval=%d)", job_key, elapsed_min, config.interval_minutes)
                return False
    return True
