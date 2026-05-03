from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.exchange_rate_cache import ExchangeRateCache

logger = get_logger(__name__)

_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.min.json"


async def get_historical_usd_thb(db: AsyncSession, rate_date: date) -> Decimal | None:
    cached = await _get_cached_rate(db, rate_date)
    if cached is not None:
        return cached

    date_str = rate_date.strftime("%Y-%m-%d")
    url = _API_URL.format(date=date_str)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            raw_rate = data.get("usd", {}).get("thb")
            if raw_rate is None:
                logger.warning("exchange_rate: thb not in API response for %s", date_str)
                return None
            rate = Decimal(str(raw_rate))
            await _cache_rate(db, rate_date, rate)
            logger.info("exchange_rate: fetched USD/THB=%.4f for %s", float(rate), date_str)
            return rate
    except Exception as exc:
        logger.warning("exchange_rate: fetch failed for %s: %s", date_str, exc)
        return None


async def get_current_usd_thb(db: AsyncSession) -> Decimal | None:
    return await get_historical_usd_thb(db, datetime.now(timezone.utc).date())


async def _get_cached_rate(db: AsyncSession, rate_date: date) -> Decimal | None:
    result = await db.execute(
        select(ExchangeRateCache).where(
            ExchangeRateCache.rate_date == rate_date,
            ExchangeRateCache.from_currency == "USD",
            ExchangeRateCache.to_currency == "THB",
        )
    )
    row = result.scalar_one_or_none()
    return row.rate if row else None


async def _cache_rate(db: AsyncSession, rate_date: date, rate: Decimal) -> None:
    entry = ExchangeRateCache(
        rate_date=rate_date,
        from_currency="USD",
        to_currency="THB",
        rate=rate,
    )
    db.add(entry)
    await db.flush()
