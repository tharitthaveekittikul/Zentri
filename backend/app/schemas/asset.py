import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AssetCreate(BaseModel):
    symbol: str
    asset_type: Literal["us_stock", "thai_stock", "th_fund", "crypto", "gold"]
    name: str
    currency: str = "USD"
    metadata_: dict[str, Any] = {}


class AssetResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_type: str
    name: str
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}
