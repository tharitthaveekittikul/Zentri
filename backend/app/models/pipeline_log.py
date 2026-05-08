import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

JOB_TYPES = (
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth", "backfill_historical_prices",
    "ingest_document", "run_analysis",
    "watchlist_discovery", "watchlist_scan",
    "dividend_fetch", "ipo_fetch", "dividend_alert",
)
JOB_STATUSES = ("queued", "running", "done", "failed")


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        Enum(*JOB_TYPES, name="job_type_enum"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(*JOB_STATUSES, name="job_status_enum"), nullable=False, default="queued"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["PipelineStep"]] = relationship(  # type: ignore[name-defined]
        "PipelineStep",
        back_populates="pipeline_log",
        order_by="PipelineStep.started_at",
        lazy="raise",
    )
