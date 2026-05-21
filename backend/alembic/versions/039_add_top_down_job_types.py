"""add top_down job types to enums

Revision ID: 039
Revises: 038
Create Date: 2026-05-19
"""
from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'run_top_down_analysis'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'top_down_discovery'")


def downgrade() -> None:
    pass
