from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.watchlist_alert import check_and_notify

logger = get_logger(__name__)


async def job_check_watchlist_alerts(ctx: dict) -> dict:
    """ARQ job: check watchlist target prices and send Telegram alerts."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_alert")
        try:
            count = await check_and_notify(db)
            await finish_log(db, log, success=True)
            logger.info("Watchlist alert job done — %d alert(s) sent", count)
            return {"alerts_sent": count}
        except Exception as e:
            logger.exception("job_check_watchlist_alerts failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
