"""Preserve historical deduction rows on removal.

Revision ID: h5j9l1n3p569
Revises: h5j9l1n3p568
"""
from alembic import op
import sqlalchemy as sa

revision = "h5j9l1n3p569"
down_revision = "h5j9l1n3p568"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("legacy_bank_deductions", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("legacy_bank_deductions", sa.Column("deleted_by_user_id", sa.UUID(), nullable=True))
    op.create_index("ix_legacy_bank_deductions_deleted_at", "legacy_bank_deductions", ["deleted_at"])


def downgrade():
    op.drop_index("ix_legacy_bank_deductions_deleted_at", table_name="legacy_bank_deductions")
    op.drop_column("legacy_bank_deductions", "deleted_by_user_id")
    op.drop_column("legacy_bank_deductions", "deleted_at")
