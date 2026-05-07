from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.dividend_alert import check_and_notify
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


async def job_dividend_alert(ctx: dict) -> dict:
    """ARQ job: send Telegram alerts for ex-dividend events happening today."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "dividend_alert")
        try:
            count = await check_and_notify(db)
            await finish_log(db, log, success=True)
            logger.info("Dividend alert job done — %d alert(s) sent", count)
            return {"alerts_sent": count}
        except Exception as e:
            logger.exception("job_dividend_alert failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
