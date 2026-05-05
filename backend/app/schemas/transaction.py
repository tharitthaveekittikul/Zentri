import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    asset_id: uuid.UUID
    platform: str | None = None
    type: Literal["buy", "sell", "dividend", "reward", "fee", "transfer"]
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    executed_at: datetime


class ManualTransactionCreate(BaseModel):
    symbol: str
    asset_type: str = "us_stock"
    currency: str = "THB"
    platform: str | None = None
    type: Literal["buy", "sell", "dividend", "reward", "fee", "transfer"]
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    executed_at: datetime


class TransactionResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    platform: str | None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
