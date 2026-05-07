"""add sec_api_key to users

Revision ID: 022
Revises: 021
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("sec_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "sec_api_key")
