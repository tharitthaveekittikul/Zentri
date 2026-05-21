import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeepDiveAnalysis(Base):
    __tablename__ = "deep_dive_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    business_model: Mapped[str] = mapped_column(Text, nullable=False)
    moat_edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    moat_summary: Mapped[str] = mapped_column(Text, nullable=False)
    moat_competitors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    catalysts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    asymmetry_verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    asymmetry_floor: Mapped[str] = mapped_column(Text, nullable=False)
    asymmetry_ceiling: Mapped[str] = mapped_column(Text, nullable=False)
    asymmetry_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
