import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str = "us_stock"
    purchased_at: date | None = None
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str = "THB"


class HoldingRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    currency: str
    purchased_at: date | None
    outstanding_shares: Decimal
    cost_per_share: Decimal
    total_cost: Decimal
    current_price: Decimal | None = None
    holding_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_1d_change: Decimal | None = None

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost: Decimal
    primary_currency: str
