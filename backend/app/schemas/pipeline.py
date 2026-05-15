import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth", "backfill_historical_prices",
    "watchlist_discovery", "watchlist_scan", "watchlist_alert",
    "run_analysis", "ingest_document",
    "dividend_fetch", "dividend_alert", "ipo_fetch",
]
JobStatus = Literal["queued", "running", "done", "failed"]
StepStatus = Literal["running", "done", "failed"]


class PipelineStepResponse(BaseModel):
    id: uuid.UUID
    pipeline_log_id: uuid.UUID
    step_name: str
    status: StepStatus
    started_at: datetime
    finished_at: datetime | None
    metadata: dict | None = Field(None, validation_alias="step_metadata")
    error_message: str | None

    model_config = {"from_attributes": True, "populate_by_name": True}


class PipelineLogResponse(BaseModel):
    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    steps: list[PipelineStepResponse] = []

    model_config = {"from_attributes": True}
