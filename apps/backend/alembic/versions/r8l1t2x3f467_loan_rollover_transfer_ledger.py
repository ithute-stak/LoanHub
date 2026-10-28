"""Add durable loan rollover transfer ledger.

Revision ID: r8l1t2x3f467
Revises: c7d2h4s6t820
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r8l1t2x3f467"
down_revision = "c7d2h4s6t820"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loan_rollover_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=36)),
        sa.Column("updated_by", sa.String(length=36)),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_loan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("child_loan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_installment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repayment_installments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_reference", sa.String(length=160), nullable=False),
        sa.Column("agreement_reference", sa.String(length=180), nullable=False),
        sa.Column("approval_reference", sa.String(length=180), nullable=False),
        sa.Column("principal_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("interest_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("fee_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("transfer_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("posted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("company_id", "transfer_reference", name="uq_rollover_company_transfer_ref"),
        sa.UniqueConstraint("parent_loan_id", name="uq_rollover_once_per_parent"),
        sa.UniqueConstraint("child_loan_id", name="uq_rollover_once_per_child"),
        sa.CheckConstraint("transfer_amount > 0", name="ck_rollover_positive_amount"),
        sa.CheckConstraint("principal_component >= 0 AND interest_component >= 0 AND fee_component >= 0", name="ck_rollover_nonnegative_components"),
        sa.CheckConstraint("transfer_amount = principal_component + interest_component + fee_component", name="ck_rollover_component_sum"),
        sa.CheckConstraint("parent_loan_id <> child_loan_id", name="ck_rollover_distinct_loans"),
    )
    op.create_index("ix_loan_rollover_transfers_company_id", "loan_rollover_transfers", ["company_id"])


def downgrade():
    op.drop_index("ix_loan_rollover_transfers_company_id", table_name="loan_rollover_transfers")
    op.drop_table("loan_rollover_transfers")
