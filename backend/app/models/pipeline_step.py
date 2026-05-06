import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("running", "done", "failed", name="pipeline_step_status_enum"),
        nullable=False,
        default="running",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    step_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True, name="metadata")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_log: Mapped["PipelineLog"] = relationship(  # type: ignore[name-defined]
        "PipelineLog", back_populates="steps"
    )
