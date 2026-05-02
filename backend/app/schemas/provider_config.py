from __future__ import annotations
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

PROVIDER_LITERAL = Literal["anthropic", "openai", "gemini", "ollama", "openrouter"]


class ProviderConfigCreate(BaseModel):
    provider: PROVIDER_LITERAL
    api_key: str | None = None
    host_url: str | None = None


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = None
    host_url: str | None = None


class ProviderConfigOut(BaseModel):
    id: uuid.UUID
    provider: str
    host_url: str | None
    is_connected: bool
    models_cache: list[str]
    models_fetched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
