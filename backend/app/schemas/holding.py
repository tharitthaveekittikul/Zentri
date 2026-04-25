import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    asset_id: uuid.UUID
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str = "USD"


class HoldingResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost_usd: Decimal
