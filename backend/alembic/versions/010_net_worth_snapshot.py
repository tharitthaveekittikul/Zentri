"""add net worth snapshots table

Revision ID: 010
Revises: 009
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_value_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_net_worth_snapshots_user_date", "net_worth_snapshots", ["user_id", "snapshot_date"])
    op.create_unique_constraint("uq_net_worth_snapshots_user_date", "net_worth_snapshots", ["user_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_constraint("uq_net_worth_snapshots_user_date", "net_worth_snapshots", type_="unique")
    op.drop_index("ix_net_worth_snapshots_user_date", "net_worth_snapshots")
    op.drop_table("net_worth_snapshots")
