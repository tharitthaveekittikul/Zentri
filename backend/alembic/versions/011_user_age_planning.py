"""add birth_date and plan_to_age to users

Revision ID: 011
Revises: 010
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("plan_to_age", sa.Integer(), nullable=True, server_default="85"))


def downgrade() -> None:
    op.drop_column("users", "plan_to_age")
    op.drop_column("users", "birth_date")
