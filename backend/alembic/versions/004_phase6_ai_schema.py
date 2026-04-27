"""phase 6 AI/LLM analysis schema

Revision ID: 004
Revises: 003
Create Date: 2026-04-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend existing job_type_enum
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'ingest_document'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'run_analysis'")

    op.create_table(
        "llm_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=True),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("file_path", sa.String, nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("chroma_collection_id", sa.String, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ai_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("target_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("tokens_in", sa.Integer, default=0),
        sa.Column("tokens_out", sa.Integer, default=0),
        sa.Column("cost_usd", sa.Numeric(10, 6), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "llm_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_id", UUID(as_uuid=True), sa.ForeignKey("ai_analyses.id"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_order", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_conversations")
    op.drop_table("ai_analyses")
    op.drop_table("documents")
    op.drop_table("llm_settings")
