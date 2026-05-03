import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportTemplate(Base):
    __tablename__ = "import_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    json_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    column_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    field_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    asset_type_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    asset_type_fallback: Mapped[str] = mapped_column(String(30), nullable=False)
    currency_default: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
    value_transforms: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    derived_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    defaults: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
