"""price feed and pipeline schema

Revision ID: 003
Revises: 002
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_type_enum AS ENUM (
                'price_fetch_us', 'price_fetch_crypto',
                'price_fetch_gold', 'price_fetch_benchmark'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status_enum AS ENUM ('queued', 'running', 'done', 'failed');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)

    # --- prices table (will become TimescaleDB hypertable) ---
    op.create_table(
        "prices",
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=True),
        sa.Column("high", sa.Numeric(20, 8), nullable=True),
        sa.Column("low", sa.Numeric(20, 8), nullable=True),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.PrimaryKeyConstraint("asset_id", "timestamp"),
    )
    op.create_index("ix_prices_asset_timestamp", "prices", ["asset_id", "timestamp"])
    op.execute(
        "SELECT create_hypertable('prices', 'timestamp', if_not_exists => TRUE)"
    )

    # --- pipeline_logs table ---
    op.create_table(
        "pipeline_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "job_type",
            PG_ENUM(name="job_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            PG_ENUM(name="job_status_enum", create_type=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_pipeline_logs_started_at", "pipeline_logs", ["started_at"])

    # --- benchmarks table ---
    op.create_table(
        "benchmarks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.execute("""
        INSERT INTO benchmarks (symbol, name) VALUES
            ('^GSPC', 'S&P 500'),
            ('^SET.BK', 'SET Index')
        ON CONFLICT (symbol) DO NOTHING
    """)

    # --- benchmark_prices table (hypertable) ---
    op.create_table(
        "benchmark_prices",
        sa.Column("benchmark_id", UUID(as_uuid=True), sa.ForeignKey("benchmarks.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=True),
        sa.Column("high", sa.Numeric(20, 8), nullable=True),
        sa.Column("low", sa.Numeric(20, 8), nullable=True),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.PrimaryKeyConstraint("benchmark_id", "timestamp"),
    )
    op.execute(
        "SELECT create_hypertable('benchmark_prices', 'timestamp', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("benchmark_prices")
    op.drop_table("benchmarks")
    op.drop_index("ix_pipeline_logs_started_at", table_name="pipeline_logs")
    op.drop_table("pipeline_logs")
    op.drop_index("ix_prices_asset_timestamp", table_name="prices")
    op.drop_table("prices")
    op.execute("DROP TYPE job_status_enum")
    op.execute("DROP TYPE job_type_enum")
