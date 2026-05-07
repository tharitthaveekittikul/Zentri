"""add ipo_fetch to job_type_enum

Revision ID: 028
Revises: 027
Create Date: 2026-05-08
"""
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'ipo_fetch'")


def downgrade() -> None:
    pass
