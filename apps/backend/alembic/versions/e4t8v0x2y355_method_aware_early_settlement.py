"""method-aware early settlement quotes and audit trail

Revision ID: e4t8v0x2y355
Revises: d3s7u9w1x244
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4t8v0x2y355"
down_revision: Union[str, Sequence[str], None] = "d3s7u9w1x244"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loan_early_settlements",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quoted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="quoted", nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("quote_expires_at", sa.DateTime(), nullable=False),
        sa.Column("calculation_method", sa.String(length=40), nullable=False),
        sa.Column("original_term_months", sa.Integer(), nullable=False),
        sa.Column("chargeable_periods", sa.Integer(), nullable=False),
        sa.Column("original_maturity_date", sa.Date(), nullable=True),
        sa.Column("original_principal", sa.Numeric(15, 2), nullable=False),
        sa.Column("original_total_repayable", sa.Numeric(15, 2), nullable=False),
        sa.Column("original_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("original_amount_paid", sa.Numeric(15, 2), nullable=False),
        sa.Column("original_total_interest", sa.Numeric(15, 2), nullable=False),
        sa.Column("earned_interest", sa.Numeric(15, 2), nullable=False),
        sa.Column("unearned_interest_rebate", sa.Numeric(15, 2), nullable=False),
        sa.Column("processing_fee_retained", sa.Numeric(15, 2), nullable=False),
        sa.Column("payments_received", sa.Numeric(15, 2), nullable=False),
        sa.Column("revised_total_repayable", sa.Numeric(15, 2), nullable=False),
        sa.Column("settlement_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("settlement_principal", sa.Numeric(15, 2), nullable=False),
        sa.Column("settlement_interest", sa.Numeric(15, 2), nullable=False),
        sa.Column("settlement_fees", sa.Numeric(15, 2), nullable=False),
        sa.Column("overpayment_credit", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("borrower_acknowledged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("agreement_note", sa.Text(), nullable=True),
        sa.Column("agreement_reference", sa.String(length=160), nullable=True),
        sa.Column("calculation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("installment_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quoted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["settled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('quoted','processing','settled','failed','expired','reversed')",
            name="ck_early_settlement_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id"),
    )
    op.create_index(
        "uq_early_settlement_open_loan",
        "loan_early_settlements",
        ["loan_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('quoted','processing')"),
    )
    for name, columns, unique in (
        ("ix_early_settlement_company", ["company_id"], False),
        ("ix_early_settlement_borrower", ["borrower_id"], False),
        ("ix_early_settlement_loan", ["loan_id"], False),
        ("ix_early_settlement_payment", ["payment_id"], True),
        ("ix_early_settlement_status", ["status"], False),
        ("ix_early_settlement_date", ["settlement_date"], False),
        ("ix_early_settlement_expiry", ["quote_expires_at"], False),
    ):
        op.create_index(name, "loan_early_settlements", columns, unique=unique)


def downgrade() -> None:
    op.drop_index("uq_early_settlement_open_loan", table_name="loan_early_settlements")
    for name in (
        "ix_early_settlement_expiry",
        "ix_early_settlement_date",
        "ix_early_settlement_status",
        "ix_early_settlement_payment",
        "ix_early_settlement_loan",
        "ix_early_settlement_borrower",
        "ix_early_settlement_company",
    ):
        op.drop_index(name, table_name="loan_early_settlements")
    op.drop_table("loan_early_settlements")
