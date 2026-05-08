import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OverviewAnalysis(Base):
    __tablename__ = "overview_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    grade: Mapped[str] = mapped_column(nullable=False)
    health: Mapped[str] = mapped_column(nullable=False)
    portfolio_adherence_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    insights: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    top_action: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    cost_thb: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
