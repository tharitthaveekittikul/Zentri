"""add dividend_alert to job_type_enum

Revision ID: 030
Revises: 029
Create Date: 2026-05-08
"""
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'dividend_alert'")


def downgrade() -> None:
    pass
