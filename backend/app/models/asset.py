import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ASSET_TYPES = ("us_stock", "thai_stock", "thai_dr", "th_fund", "etf", "crypto", "gold", "cash")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        Enum(*ASSET_TYPES, name="asset_type_enum"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
