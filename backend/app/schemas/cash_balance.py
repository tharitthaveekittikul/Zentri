from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, field_validator


class CashBalanceCreate(BaseModel):
    asset_id: uuid.UUID
    balance: float
    snapshot_date: date
    notes: str | None = None


class CashBalanceOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    balance: float
    snapshot_date: date
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("balance", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v
