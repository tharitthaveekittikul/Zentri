from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.exchange_rate_cache import ExchangeRateCache

logger = get_logger(__name__)

_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.min.json"


async def get_rate(
    db: AsyncSession,
    from_currency: str,
    to_currency: str,
    rate_date: date | None = None,
) -> Decimal | None:
    """Return the rate to convert 1 unit of from_currency into to_currency.
    Uses USD as triangulation base via the free currency API."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return Decimal("1")

    if rate_date is None:
        rate_date = datetime.now(timezone.utc).date()

    cached = await _get_cached_rate(db, rate_date, from_currency, to_currency)
    if cached is not None:
        return cached

    usd_to_from = await _fetch_usd_to(db, rate_date, from_currency)
    usd_to_to = await _fetch_usd_to(db, rate_date, to_currency)

    if usd_to_from is None or usd_to_to is None:
        return None

    # from→to = (USD→to) / (USD→from)
    rate = usd_to_to / usd_to_from
    await _cache_rate(db, rate_date, from_currency, to_currency, rate)
    logger.info("exchange_rate: %s→%s=%.6f for %s", from_currency, to_currency, float(rate), rate_date)
    return rate


async def _fetch_usd_to(db: AsyncSession, rate_date: date, to_currency: str) -> Decimal | None:
    """Get USD→to_currency rate, using cache or live API."""
    to_currency = to_currency.upper()

    if to_currency == "USD":
        return Decimal("1")

    cached = await _get_cached_rate(db, rate_date, "USD", to_currency)
    if cached is not None:
        return cached

    candidates = [rate_date, rate_date - timedelta(days=1)]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for fetch_date in candidates:
            date_str = fetch_date.strftime("%Y-%m-%d")
            url = _API_URL.format(date=date_str)
            try:
                resp = await client.get(url)
                if resp.status_code == 404:
                    logger.info("exchange_rate: %s not published yet, trying previous day", date_str)
                    continue
                resp.raise_for_status()
                data = resp.json()
                raw_rate = data.get("usd", {}).get(to_currency.lower())
                if raw_rate is None:
                    logger.warning("exchange_rate: %s not in API response for %s", to_currency, date_str)
                    return None
                rate = Decimal(str(raw_rate))
                await _cache_rate(db, rate_date, "USD", to_currency, rate)
                logger.info("exchange_rate: USD→%s=%.6f for %s", to_currency, float(rate), date_str)
                return rate
            except Exception as exc:
                logger.warning("exchange_rate: fetch failed for %s on %s: %s", to_currency, date_str, exc)
                return None
    logger.warning("exchange_rate: no data available for %s or previous day", to_currency)
    return None


# Backward-compat wrappers
async def get_historical_usd_thb(db: AsyncSession, rate_date: date) -> Decimal | None:
    return await _fetch_usd_to(db, rate_date, "THB")


async def get_current_usd_thb(db: AsyncSession) -> Decimal | None:
    return await _fetch_usd_to(db, datetime.now(timezone.utc).date(), "THB")


async def _get_cached_rate(
    db: AsyncSession, rate_date: date, from_currency: str, to_currency: str
) -> Decimal | None:
    result = await db.execute(
        select(ExchangeRateCache).where(
            ExchangeRateCache.rate_date == rate_date,
            ExchangeRateCache.from_currency == from_currency,
            ExchangeRateCache.to_currency == to_currency,
        )
    )
    row = result.scalar_one_or_none()
    return row.rate if row else None


async def _cache_rate(
    db: AsyncSession, rate_date: date, from_currency: str, to_currency: str, rate: Decimal
) -> None:
    stmt = (
        pg_insert(ExchangeRateCache)
        .values(
            rate_date=rate_date,
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
        )
        .on_conflict_do_nothing()
    )
    await db.execute(stmt)
    await db.flush()
