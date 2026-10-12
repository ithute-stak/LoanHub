"""Store imported legacy bank deductions without posting loans.

Revision ID: h5j9l1n3p568
Revises: h5j9l1n3p567
"""
from alembic import op
import sqlalchemy as sa

revision = "h5j9l1n3p568"
down_revision = "h5j9l1n3p567"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legacy_bank_deductions",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("loan_companies.id"), nullable=False),
        sa.Column("work_group_id", sa.UUID(), sa.ForeignKey("employer_groups.id"), nullable=False),
        sa.Column("client_name", sa.String(120), nullable=False),
        sa.Column("account_number_encrypted", sa.String(500), nullable=False),
        sa.Column("account_last4", sa.String(4), nullable=False),
        sa.Column("branch_code", sa.String(6), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_legacy_bank_deduction_positive"),
    )
    op.create_index("ix_legacy_bank_deductions_company_id", "legacy_bank_deductions", ["company_id"])


def downgrade():
    op.drop_index("ix_legacy_bank_deductions_company_id", table_name="legacy_bank_deductions")
    op.drop_table("legacy_bank_deductions")
