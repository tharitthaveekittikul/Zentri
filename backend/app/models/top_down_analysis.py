import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TopDownAnalysis(Base):
    __tablename__ = "top_down_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    mega_trend: Mapped[str] = mapped_column(Text, nullable=False)
    financial_health: Mapped[str] = mapped_column(Text, nullable=False)
    swot_strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_opportunities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_threats: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    verdict: Mapped[str] = mapped_column(String(10), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    ath_drop_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
