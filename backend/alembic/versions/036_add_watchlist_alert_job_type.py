"""add watchlist_alert to job_type_enum

Revision ID: 036
Revises: 035
Create Date: 2026-05-15
"""
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'watchlist_alert'")


def downgrade() -> None:
    pass
