"""add dividend events table

Revision ID: 013
Revises: 012
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dividend_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("amount_per_share", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("frequency", sa.String(20), nullable=True),
        sa.Column(
            "status",
            sa.Enum("upcoming", "payable", "paid", name="dividend_event_status_enum"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="yfinance"),
        sa.Column("confirmed_transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dividend_events_asset_ex_date", "dividend_events", ["asset_id", "ex_date"])
    op.create_unique_constraint("uq_dividend_events_asset_ex_date", "dividend_events", ["asset_id", "ex_date"])


def downgrade() -> None:
    op.drop_constraint("uq_dividend_events_asset_ex_date", "dividend_events", type_="unique")
    op.drop_index("ix_dividend_events_asset_ex_date", "dividend_events")
    op.drop_table("dividend_events")
    op.execute("DROP TYPE IF EXISTS dividend_event_status_enum")
