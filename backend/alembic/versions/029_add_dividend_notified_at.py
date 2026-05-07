"""add dividend_notified_at to dividend_events

Revision ID: 029
Revises: 028
Create Date: 2026-05-08
"""
import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dividend_events",
        sa.Column("dividend_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dividend_events", "dividend_notified_at")
