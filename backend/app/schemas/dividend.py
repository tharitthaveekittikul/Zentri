import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


class DividendEventOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    ex_date: date
    pay_date: Optional[date] = None
    record_date: Optional[date] = None
    amount_per_share: Decimal
    currency: str
    frequency: Optional[str] = None
    status: str
    source: str
    quantity_held: Decimal
    projected_total_usd: Decimal
    projected_total_secondary: Optional[Decimal] = None

    model_config = {"from_attributes": False}


class DividendMonthGroup(BaseModel):
    year: int
    month: int
    total_projected_usd: Decimal
    events: list[DividendEventOut]


class DividendCalendarResponse(BaseModel):
    months: list[DividendMonthGroup]


class DividendConfirmRequest(BaseModel):
    quantity: Decimal
    executed_at: date
