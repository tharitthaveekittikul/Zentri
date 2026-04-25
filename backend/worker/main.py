from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from worker.jobs.price_fetch import (
    job_fetch_benchmark_prices,
    job_fetch_price_gold,
    job_fetch_prices_crypto,
    job_fetch_prices_us,
)

setup_logging()
logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    """Create async DB session factory and attach to worker context."""
    engine = create_async_engine(settings.DATABASE_URL)
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("ARQ worker started — DB pool ready")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    functions = [
        job_fetch_prices_us,
        job_fetch_prices_crypto,
        job_fetch_price_gold,
        job_fetch_benchmark_prices,
    ]
    cron_jobs = [
        cron(job_fetch_prices_us, minute={0, 15, 30, 45}),
        cron(job_fetch_prices_crypto, minute={0, 15, 30, 45}),
        cron(job_fetch_price_gold, minute={0, 15, 30, 45}),
        cron(job_fetch_benchmark_prices, minute=0),
    ]
