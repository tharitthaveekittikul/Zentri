import uuid
from datetime import datetime

from pydantic import BaseModel


class PlatformCreate(BaseModel):
    name: str
    asset_types_supported: list[str] = []
    notes: str | None = None


class PlatformUpdate(BaseModel):
    name: str
    asset_types_supported: list[str] = []
    notes: str | None = None


class PlatformResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_types_supported: list[str]
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
