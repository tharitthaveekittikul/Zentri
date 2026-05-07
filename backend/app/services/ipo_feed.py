import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.ipo_event import IpoEvent
from app.models.watchlist_item import WatchlistItem

logger = get_logger(__name__)


def extract_ipo_info(symbol: str, info: dict) -> Optional[dict]:
    """Extract IPO information from yfinance ticker info.

    Args:
        symbol: Stock symbol
        info: Dictionary from yf.Ticker(symbol).info

    Returns:
        Dictionary with IPO data or None if invalid/past date
    """
    raw_date = info.get("ipoDate")
    if not raw_date:
        return None
    try:
        ipo_date = date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return None
    cutoff = date.today() - timedelta(days=90)
    if ipo_date < cutoff:
        return None
    return {
        "symbol": symbol,
        "company_name": info.get("longName") or info.get("shortName"),
        "ipo_date": ipo_date,
        "price_low": Decimal(str(info["fiftyTwoWeekLow"])) if info.get("fiftyTwoWeekLow") else None,
        "price_high": Decimal(str(info["fiftyTwoWeekHigh"])) if info.get("fiftyTwoWeekHigh") else None,
        "sector": info.get("sector"),
        "status": "upcoming" if ipo_date >= date.today() else "listed",
        "source": "yfinance",
    }


async def refresh_ipos_from_watchlist(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Refresh IPO data for all symbols in user's watchlist.

    Args:
        db: AsyncSession database connection
        user_id: User UUID

    Returns:
        Number of rows upserted
    """
    result = await db.execute(
        select(Asset.symbol)
        .join(WatchlistItem, WatchlistItem.asset_id == Asset.id)
        .where(WatchlistItem.user_id == user_id)
    )
    symbols = [row[0] for row in result.fetchall()]
    if not symbols:
        return 0

    upserted = 0
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info
            data = extract_ipo_info(symbol, info)
            if not data:
                continue
            stmt = (
                pg_insert(IpoEvent)
                .values(id=uuid.uuid4(), **data)
                .on_conflict_do_update(
                    constraint="uq_ipo_events_symbol_date",
                    set_={k: v for k, v in data.items() if k not in ("symbol", "ipo_date")},
                )
            )
            await db.execute(stmt)
            upserted += 1
        except Exception as exc:
            logger.warning("Failed to fetch IPO data for %s: %s", symbol, exc)
    await db.commit()
    logger.info("refresh_ipos_from_watchlist: upserted %d rows for user %s", upserted, user_id)
    return upserted


async def get_ipo_events(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Get IPO events within date range, marked with watchlist status.

    Args:
        db: AsyncSession database connection
        user_id: User UUID (for watchlist lookup)
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        List of IPO event dictionaries with is_in_watchlist flag
    """
    result = await db.execute(
        select(IpoEvent).where(
            IpoEvent.ipo_date >= start_date,
            IpoEvent.ipo_date <= end_date,
        )
    )
    events = result.scalars().all()

    watchlist_result = await db.execute(
        select(Asset.symbol)
        .join(WatchlistItem, WatchlistItem.asset_id == Asset.id)
        .where(WatchlistItem.user_id == user_id)
    )
    watchlist_symbols = {row[0] for row in watchlist_result.fetchall()}

    return [
        {
            "id": ev.id,
            "symbol": ev.symbol,
            "company_name": ev.company_name,
            "ipo_date": ev.ipo_date,
            "price_low": ev.price_low,
            "price_high": ev.price_high,
            "sector": ev.sector,
            "status": ev.status,
            "source": ev.source,
            "is_in_watchlist": ev.symbol in watchlist_symbols,
        }
        for ev in events
    ]


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> IpoEvent | None:
    """Get a single IPO event by ID.

    Args:
        db: AsyncSession database connection
        event_id: Event UUID

    Returns:
        IpoEvent model instance or None if not found
    """
    result = await db.execute(select(IpoEvent).where(IpoEvent.id == event_id))
    return result.scalar_one_or_none()
