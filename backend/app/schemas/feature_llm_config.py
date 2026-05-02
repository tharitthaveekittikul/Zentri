from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class FeatureLLMConfigCreate(BaseModel):
    feature_key: str
    provider_config_id: uuid.UUID
    model: str
    system_prompt: str | None = None  # defaults to DEFAULT_SYSTEM_PROMPTS[feature_key]


class FeatureLLMConfigUpdate(BaseModel):
    provider_config_id: uuid.UUID | None = None
    model: str | None = None
    system_prompt: str | None = None

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_not_empty(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            raise ValueError(
                "system_prompt cannot be empty. Use /reset-prompt to restore the default."
            )
        return v


class FeatureLLMConfigOut(BaseModel):
    id: uuid.UUID
    feature_key: str
    provider_config_id: uuid.UUID
    model: str
    system_prompt: str
    is_prompt_customized: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
