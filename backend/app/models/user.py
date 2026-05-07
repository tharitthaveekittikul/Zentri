import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    currency_primary: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
    currency_secondary: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    birth_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True, default=None)
    plan_to_age: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True, server_default="85")
    telegram_bot_token: Mapped[str | None] = mapped_column(Text(), nullable=True, default=None)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    privacy_mode: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    sec_api_key: Mapped[str | None] = mapped_column(Text(), nullable=True, default=None)
