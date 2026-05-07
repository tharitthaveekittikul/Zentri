import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.ipo_feed import refresh_ipos_from_watchlist
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


async def job_fetch_ipos(ctx: dict, user_id: str) -> dict:
    """ARQ job: fetch IPO events for all symbols in a user's watchlist via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "ipo_fetch")
        try:
            count = await refresh_ipos_from_watchlist(db, uuid.UUID(user_id))
            await finish_log(db, log, success=True)
            return {"upserted": count}
        except Exception as e:
            logger.exception("job_fetch_ipos failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
