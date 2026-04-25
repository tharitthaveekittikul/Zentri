import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PriceBar(BaseModel):
    timestamp: datetime
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    volume: Decimal | None

    model_config = {"from_attributes": True}


class PriceHistoryResponse(BaseModel):
    asset_id: uuid.UUID
    bars: list[PriceBar]
