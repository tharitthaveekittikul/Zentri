from datetime import date
from decimal import Decimal
from typing import Literal, Optional, Union
import uuid

from pydantic import BaseModel


class DividendCalendarEvent(BaseModel):
    event_type: Literal["dividend"] = "dividend"
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID
    event_date: date
    pay_date: Optional[date] = None
    amount_per_share: Decimal
    currency: str
    status: str
    projected_total_usd: Decimal
    quantity_held: Decimal
    is_in_watchlist: bool = False
    asset_type: str = "us_stock"
    metadata_: dict = {}


class IpoCalendarEvent(BaseModel):
    event_type: Literal["ipo"] = "ipo"
    id: uuid.UUID
    symbol: str
    event_date: date
    company_name: Optional[str] = None
    price_low: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    sector: Optional[str] = None
    status: str
    is_in_watchlist: bool = False
    asset_type: Optional[str] = None
    metadata_: dict = {}


CalendarEvent = Union[DividendCalendarEvent, IpoCalendarEvent]


class EventsMonthGroup(BaseModel):
    year: int
    month: int
    events: list[CalendarEvent]


class EventsCalendarResponse(BaseModel):
    months: list[EventsMonthGroup]
