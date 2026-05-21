"""add ath_drop_pct to top_down_analyses

Revision ID: 038
Revises: 037
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("top_down_analyses", sa.Column("ath_drop_pct", sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("top_down_analyses", "ath_drop_pct")
