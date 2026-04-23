from arq.connections import RedisSettings

from app.core.config import settings


async def startup(ctx: dict) -> None:
    """Called when worker starts. Use for DB pool, HTTP clients, etc."""
    pass


async def shutdown(ctx: dict) -> None:
    """Called when worker stops. Clean up resources."""
    pass


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    functions = []   # Jobs added here as phases progress
    cron_jobs = []   # Scheduled jobs added here
