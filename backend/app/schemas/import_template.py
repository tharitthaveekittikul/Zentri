from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ImportTemplateOut(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    file_format: str
    json_path: str | None
    column_signature: str
    field_map: dict
    asset_type_rules: list
    asset_type_fallback: str
    currency_default: str
    value_transforms: dict
    derived_fields: dict
    defaults: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeResponse(BaseModel):
    signature: str
    structure: dict
    template_status: str  # "match" | "mismatch" | "new"
    template: ImportTemplateOut | None
    preview_rows: list[dict] | None  # populated if template matches
    matched_platform_id: uuid.UUID | None = None  # set when signature lookup finds a match


class TemplateSaveRequest(BaseModel):
    platform_id: uuid.UUID
    file_format: str
    json_path: str | None = None
    signature: str
    template_data: dict


class ConfirmImportRequest(BaseModel):
    platform_id: uuid.UUID
    rows: list[dict]  # normalized canonical rows after user review
