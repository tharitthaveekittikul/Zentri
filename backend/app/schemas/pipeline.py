import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark"
]
JobStatus = Literal["queued", "running", "done", "failed"]


class PipelineLogResponse(BaseModel):
    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}
