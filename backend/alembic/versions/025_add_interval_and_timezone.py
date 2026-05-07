"""add interval_minutes to price_schedule_config, schedule_timezone to users

Revision ID: 025
Revises: 024
Create Date: 2026-05-07
"""
import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "price_schedule_config",
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "schedule_timezone",
            sa.String(100),
            nullable=False,
            server_default="Asia/Bangkok",
        ),
    )


def downgrade() -> None:
    op.drop_column("price_schedule_config", "interval_minutes")
    op.drop_column("users", "schedule_timezone")
