"""Add reversible company legacy-loan lock configuration.

Revision ID: b4c5d6e7f801
Revises: a2b3c4d5e734
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f801"
down_revision = "a2b3c4d5e734"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_loan_settings", sa.Column(
        "legacy_loan_lock_enabled", sa.Boolean(), nullable=False,
        server_default=sa.false(),
    ))


def downgrade():
    op.drop_column("company_loan_settings", "legacy_loan_lock_enabled")
