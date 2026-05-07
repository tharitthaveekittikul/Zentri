import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceScheduleConfig(Base):
    __tablename__ = "price_schedule_config"
    __table_args__ = (UniqueConstraint("user_id", "job_key", name="uq_user_job_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    job_key: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    days: Mapped[list] = mapped_column(JSONB(), nullable=False, default=list)
    run_at_hour: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    run_at_minute: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    interval_minutes: Mapped[int | None] = mapped_column(Integer(), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
