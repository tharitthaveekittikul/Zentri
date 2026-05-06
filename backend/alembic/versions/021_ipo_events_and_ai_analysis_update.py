"""ipo_events_and_ai_analysis_update

Revision ID: 021
Revises: 020
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the ipo_event_status_enum type (DO block guards against partial prior runs)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ipo_event_status_enum AS ENUM ('upcoming', 'priced', 'listed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create ipo_events table
    op.create_table(
        "ipo_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("ipo_date", sa.Date(), nullable=False),
        sa.Column("price_low", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("price_high", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("upcoming", "priced", "listed", name="ipo_event_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "ipo_date", name="uq_ipo_events_symbol_date"),
    )
    op.create_index(op.f("ix_ipo_events_symbol"), "ipo_events", ["symbol"], unique=False)

    # Make ai_analyses.asset_id nullable
    op.alter_column("ai_analyses", "asset_id", existing_type=sa.UUID(), nullable=True)

    # Add ipo_event_id FK column to ai_analyses
    op.add_column("ai_analyses", sa.Column("ipo_event_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "ai_analyses_ipo_event_id_fkey",
        "ai_analyses",
        "ipo_events",
        ["ipo_event_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("ai_analyses_ipo_event_id_fkey", "ai_analyses", type_="foreignkey")
    op.drop_column("ai_analyses", "ipo_event_id")
    op.alter_column("ai_analyses", "asset_id", existing_type=sa.UUID(), nullable=False)
    op.drop_index(op.f("ix_ipo_events_symbol"), table_name="ipo_events")
    op.drop_table("ipo_events")
    op.execute("DROP TYPE IF EXISTS ipo_event_status_enum")
