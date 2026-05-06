import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

IPO_EVENT_STATUSES = ("upcoming", "priced", "listed")


class IpoEvent(Base):
    __tablename__ = "ipo_events"
    __table_args__ = (UniqueConstraint("symbol", "ipo_date", name="uq_ipo_events_symbol_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ipo_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    price_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*IPO_EVENT_STATUSES, name="ipo_event_status_enum"), nullable=False, default="upcoming"
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
