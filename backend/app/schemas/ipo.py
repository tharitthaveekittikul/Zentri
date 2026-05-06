import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class IpoEventOut(BaseModel):
    id: uuid.UUID
    symbol: str
    company_name: Optional[str] = None
    ipo_date: date
    price_low: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    sector: Optional[str] = None
    status: str
    source: str
    is_in_watchlist: bool = False

    model_config = {"from_attributes": False}


class IpoAnalysisResult(BaseModel):
    verdict: str
    suggested_price: Optional[Decimal] = None
    reasoning: str
    provider: str
    model: str
    cached: bool = False
