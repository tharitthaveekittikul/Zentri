import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssetSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    asset_type: str
    metadata_: dict = {}
    model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(BaseModel):
    asset_id: uuid.UUID
    target_price: Decimal | None = None
    currency: str = "USD"
    notes: str | None = None


class WatchlistItemUpdate(BaseModel):
    target_price: Decimal | None = None
    notes: str | None = None
    alert_enabled: bool | None = None
    ath_alert_threshold: Decimal | None = None


class WatchlistItemOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    target_price: Decimal | None
    currency: str
    notes: str | None
    alert_enabled: bool
    alerted_at: datetime | None
    ath_alert_threshold: Decimal | None
    ath_alerted_at: datetime | None
    created_at: datetime
    asset: AssetSummary
    current_price: Decimal | None
    pct_from_target: float | None
    ath_drop_pct: float | None
    last_verdict: str | None = None
    ai_suggested_price: Decimal | None = None
    last_scanned_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class WatchlistSuggestionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID | None
    reasoning: str
    suggested_price: Decimal | None
    verdict: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
