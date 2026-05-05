"""rename import_template_generator to import_translator in feature_llm_configs

Revision ID: 008
Revises: 007
Create Date: 2026-05-05
"""
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE feature_llm_configs "
        "SET feature_key = 'import_translator' "
        "WHERE feature_key = 'import_template_generator'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE feature_llm_configs "
        "SET feature_key = 'import_template_generator' "
        "WHERE feature_key = 'import_translator'"
    )
