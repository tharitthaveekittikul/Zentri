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
    platform: str | None = None
    metadata_: dict | None = None


class HoldingUpdate(BaseModel):
    quantity: Decimal | None = None
    avg_cost_price: Decimal | None = None
    currency: str | None = None
    platform: str | None = None


class HoldingRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    currency: str
    platform: str | None = None
    purchased_at: date | None
    outstanding_shares: Decimal
    cost_per_share: Decimal
    total_cost: Decimal
    current_price: Decimal | None = None
    holding_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_1d_change: Decimal | None = None
    metadata_: dict = {}

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost: Decimal
    total_cost_secondary: Decimal | None = None
    primary_currency: str
    secondary_currency: str
    exchange_rate: Decimal | None = None
    exchange_rate_date: str | None = None
