"""Store employer per legacy bank instruction.

Revision ID: h5j9l1n3p570
Revises: h5j9l1n3p569
"""
from alembic import op
import sqlalchemy as sa

revision = "h5j9l1n3p570"
down_revision = "h5j9l1n3p569"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("legacy_bank_deductions", sa.Column("employer", sa.String(length=120), nullable=True))
    op.create_index("ix_legacy_bank_deductions_employer", "legacy_bank_deductions", ["employer"])


def downgrade():
    op.drop_index("ix_legacy_bank_deductions_employer", table_name="legacy_bank_deductions")
    op.drop_column("legacy_bank_deductions", "employer")
