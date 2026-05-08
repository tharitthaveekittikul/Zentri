from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.price_feed import (
    fetch_benchmark_prices,
    fetch_crypto_prices,
    fetch_gold_price,
    fetch_historical_prices,
    fetch_th_fund_prices,
    fetch_thai_stock_prices,
    fetch_us_prices,
)
from app.services.price_schedule_config import should_run_job

logger = get_logger(__name__)


async def job_fetch_prices_us(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "us_stock"):
            logger.info("job_fetch_prices_us skipped by schedule")
            return {"skipped": True}
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


async def job_fetch_prices_crypto(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "crypto"):
            logger.info("job_fetch_prices_crypto skipped by schedule")
            return {"skipped": True}
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


async def job_fetch_price_gold(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "gold"):
            logger.info("job_fetch_price_gold skipped by schedule")
            return {"skipped": True}
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


async def job_fetch_prices_thai_stock(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch Thai stock and Thai DR prices via yfinance (.BK suffix)."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "thai_stock"):
            logger.info("job_fetch_prices_thai_stock skipped by schedule")
            return {"skipped": True}
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


async def job_fetch_prices_th_fund(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch Thai mutual fund NAV via SEC Thailand API v2."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "thai_fund"):
            logger.info("job_fetch_prices_th_fund skipped by schedule")
            return {"skipped": True}
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


async def job_fetch_benchmark_prices(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not manual and not await should_run_job(db, "benchmark"):
            logger.info("job_fetch_benchmark_prices skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_benchmark")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_benchmark_prices(db, period="2y" if manual else "5d")
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_backfill_historical_prices(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch full yfinance price history for all priced assets."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "backfill_historical_prices")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_historical_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            logger.info("job_backfill_historical_prices done: %s", result)
            return result
        except Exception as e:
            logger.exception("job_backfill_historical_prices failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
