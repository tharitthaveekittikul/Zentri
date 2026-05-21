import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CombinedVerdict(Base):
    __tablename__ = "combined_verdicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    conviction: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    risk_reward: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    bull_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    bear_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    key_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    based_on: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
