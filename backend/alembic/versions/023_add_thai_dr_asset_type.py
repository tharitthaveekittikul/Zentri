"""add thai_dr to asset_type_enum

Revision ID: 023
Revises: 022
Create Date: 2026-05-07
"""
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE asset_type_enum ADD VALUE IF NOT EXISTS 'thai_dr'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
