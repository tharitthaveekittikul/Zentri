from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.dividend_feed import fetch_all_dividends

logger = get_logger(__name__)


async def job_fetch_dividends(ctx: dict) -> dict:
    """ARQ job: fetch dividend events for all us_stock/etf assets via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "dividend_fetch")
        try:
            count = await fetch_all_dividends(db)
            await finish_log(db, log, success=True)
            return {"upserted": count}
        except Exception as e:
            logger.exception("job_fetch_dividends failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
