import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services import dividend_feed, ipo_feed

logger = get_logger(__name__)


async def get_calendar(
    db: AsyncSession,
    user_id: uuid.UUID,
    months: int,
    secondary_currency: str,
) -> dict:
    today = date.today()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=months * 31)

    dividend_result, ipo_events_raw = await asyncio.gather(
        dividend_feed.get_calendar(db, user_id, months, secondary_currency),
        ipo_feed.get_ipo_events(db, user_id, start_date, end_date),
    )

    dividend_events_raw = []
    if isinstance(dividend_result, dict):
        for month in dividend_result.get("months", []):
            dividend_events_raw.extend(month.get("events", []))

    dividend_events = [
        {
            "event_type": "dividend",
            "id": e["id"],
            "symbol": e["symbol"],
            "asset_id": e["asset_id"],
            "event_date": e["ex_date"],
            "pay_date": e.get("pay_date"),
            "amount_per_share": e["amount_per_share"],
            "currency": e["currency"],
            "status": e["status"],
            "projected_total_usd": e["projected_total_usd"],
            "quantity_held": e["quantity_held"],
            "is_in_watchlist": False,
        }
        for e in dividend_events_raw
    ]

    ipo_events = [
        {
            "event_type": "ipo",
            "id": e["id"],
            "symbol": e["symbol"],
            "event_date": e["ipo_date"],
            "company_name": e.get("company_name"),
            "price_low": e.get("price_low"),
            "price_high": e.get("price_high"),
            "sector": e.get("sector"),
            "status": e["status"],
            "is_in_watchlist": e["is_in_watchlist"],
        }
        for e in ipo_events_raw
    ]

    all_events = dividend_events + ipo_events
    return _group_by_month(all_events, start_date, end_date)


def _group_by_month(events: list[dict], start_date: date, end_date: date) -> dict:
    months: dict[tuple[int, int], list] = {}
    current = start_date.replace(day=1)
    while current <= end_date:
        months[(current.year, current.month)] = []
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    for event in events:
        d = event["event_date"]
        key = (d.year, d.month)
        if key in months:
            months[key].append(event)

    return {
        "months": [
            {"year": y, "month": m, "events": evts}
            for (y, m), evts in sorted(months.items())
        ]
    }
