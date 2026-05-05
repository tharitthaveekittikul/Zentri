"""watchlist_suggestion table

Revision ID: 017
Revises: 016
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'watchlist_discovery'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'watchlist_scan'")

    op.create_table(
        "watchlist_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("suggested_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_watchlist_suggestions_user_id", "watchlist_suggestions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_suggestions_user_id", table_name="watchlist_suggestions")
    op.drop_table("watchlist_suggestions")
