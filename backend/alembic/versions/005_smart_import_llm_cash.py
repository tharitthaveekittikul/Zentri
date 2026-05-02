"""smart import llm cash

Revision ID: 005
Revises: 004
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values — must be outside transaction in PostgreSQL
    op.execute("ALTER TYPE asset_type_enum ADD VALUE IF NOT EXISTS 'etf'")
    op.execute("ALTER TYPE asset_type_enum ADD VALUE IF NOT EXISTS 'cash'")

    op.create_table(
        "provider_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=True),
        sa.Column("host_url", sa.String(255), nullable=True),
        sa.Column("is_connected", sa.Boolean, default=False),
        sa.Column("models_cache", JSONB, nullable=False, server_default="[]"),
        sa.Column("models_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_configs_user_id", "provider_configs", ["user_id"])

    op.create_table(
        "feature_llm_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("feature_key", sa.String(60), nullable=False),
        sa.Column(
            "provider_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("provider_configs.id"),
            nullable=False,
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("is_prompt_customized", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feature_llm_configs_user_id", "feature_llm_configs", ["user_id"])

    op.create_table(
        "cash_balances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cash_balances_asset_id", "cash_balances", ["asset_id"])
    op.create_index("ix_cash_balances_user_id", "cash_balances", ["user_id"])

    op.create_table(
        "import_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("json_path", sa.String(255), nullable=True),
        sa.Column("column_signature", sa.String(64), nullable=False),
        sa.Column("field_map", JSONB, nullable=False, server_default="{}"),
        sa.Column("asset_type_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("asset_type_fallback", sa.String(30), nullable=False),
        sa.Column("currency_default", sa.String(10), nullable=False, server_default="THB"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_templates_platform_id", "import_templates", ["platform_id"])
    op.create_index("ix_import_templates_user_id", "import_templates", ["user_id"])

    op.add_column(
        "transactions",
        sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "platform_id")
    op.drop_table("import_templates")
    op.drop_table("cash_balances")
    op.drop_table("feature_llm_configs")
    op.drop_table("provider_configs")
    # Note: PostgreSQL does not support removing enum values — manual downgrade needed for etf/cash
