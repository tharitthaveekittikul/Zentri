"""add dividend_fetch to job_type_enum

Revision ID: 027
Revises: 026
Create Date: 2026-05-08
"""
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'dividend_fetch'")


def downgrade() -> None:
    pass
