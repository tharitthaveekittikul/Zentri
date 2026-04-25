from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.price_feed import (
    fetch_benchmark_prices,
    fetch_crypto_prices,
    fetch_gold_price,
    fetch_us_prices,
)

logger = get_logger(__name__)


async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_us")
        try:
            count = await fetch_us_prices(db)
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_us failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_prices_crypto(ctx: dict) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_crypto")
        try:
            count = await fetch_crypto_prices(db)
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_crypto failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_price_gold(ctx: dict) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_gold")
        try:
            count = await fetch_gold_price(db)
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_price_gold failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_benchmark_prices(ctx: dict) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_benchmark")
        try:
            count = await fetch_benchmark_prices(db)
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
