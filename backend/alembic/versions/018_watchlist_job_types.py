"""add watchlist job types to job_type_enum

Revision ID: 018
Revises: 017
Create Date: 2026-05-06
"""
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'watchlist_discovery'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'watchlist_scan'")


def downgrade() -> None:
    pass
