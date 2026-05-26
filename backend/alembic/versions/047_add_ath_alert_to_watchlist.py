"""add ath alert columns to watchlist_items

Revision ID: 047
Revises: 046
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watchlist_items",
        sa.Column("ath_alert_threshold", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "watchlist_items",
        sa.Column("ath_alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watchlist_items", "ath_alerted_at")
    op.drop_column("watchlist_items", "ath_alert_threshold")
