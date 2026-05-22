"""add sector industry market_cap_category to assets

Revision ID: 044
Revises: 043
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("sector", sa.String(100), nullable=True))
    op.add_column("assets", sa.Column("industry", sa.String(100), nullable=True))
    op.add_column("assets", sa.Column("market_cap_category", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "market_cap_category")
    op.drop_column("assets", "industry")
    op.drop_column("assets", "sector")
