"""add backfill_historical_prices job type

Revision ID: 032
Revises: 031
Create Date: 2026-05-08
"""
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'backfill_historical_prices'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing ENUM values
