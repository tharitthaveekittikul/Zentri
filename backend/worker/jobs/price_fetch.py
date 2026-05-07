from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.price_feed import (
    fetch_benchmark_prices,
    fetch_crypto_prices,
    fetch_gold_price,
    fetch_th_fund_prices,
    fetch_thai_stock_prices,
    fetch_us_prices,
)

logger = get_logger(__name__)


async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_us")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_us_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_us failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_prices_crypto(ctx: dict) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_crypto")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_crypto_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_crypto failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_price_gold(ctx: dict) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_gold")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_gold_price(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_price_gold failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_prices_thai_stock(ctx: dict) -> dict:
    """ARQ job: fetch Thai stock and Thai DR prices via yfinance (.BK suffix)."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_thai_stock")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_thai_stock_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_thai_stock failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_prices_th_fund(ctx: dict) -> dict:
    """ARQ job: fetch Thai mutual fund NAV via SEC Thailand API v2."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_th_fund")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_th_fund_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_th_fund failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_benchmark_prices(ctx: dict) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_benchmark")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_benchmark_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
