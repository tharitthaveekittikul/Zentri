"""add pipeline_steps table

Revision ID: 019
Revises: 018
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

# create_type=False tells SQLAlchemy NOT to auto-issue CREATE TYPE;
# we manage the type lifecycle ourselves with explicit DDL below.
_step_status_type = PG_ENUM(
    "running", "done", "failed",
    name="pipeline_step_status_enum",
    create_type=False,
)


def upgrade() -> None:
    # Create the enum type explicitly (idempotent via checkfirst).
    _step_status_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "pipeline_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipeline_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String, nullable=False),
        sa.Column(
            "status",
            _step_status_type,
            nullable=False,
            server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_pipeline_steps_pipeline_log_id",
        "pipeline_steps",
        ["pipeline_log_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_steps_pipeline_log_id", "pipeline_steps")
    op.drop_table("pipeline_steps")
    _step_status_type.drop(op.get_bind(), checkfirst=True)
