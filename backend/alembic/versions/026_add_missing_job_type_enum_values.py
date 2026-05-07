"""add missing job_type_enum values

Revision ID: 026
Revises: 025
Create Date: 2026-05-07
"""
from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'price_fetch_thai_stock'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'price_fetch_th_fund'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'snapshot_net_worth'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
