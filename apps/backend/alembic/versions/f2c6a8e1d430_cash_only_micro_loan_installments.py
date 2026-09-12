"""Cash-only Micro Loan Method, loan numbers and instalment evidence.

Revision ID: f2c6a8e1d430
Revises: e7b2c4d9a610
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f2c6a8e1d430"
down_revision = "e7b2c4d9a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLAlchemy persists enum member names for this project.
    op.execute("ALTER TYPE paymentprovider ADD VALUE IF NOT EXISTS 'CASH'")

    op.alter_column(
        "client_company_loan",
        "loan_reference",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    op.add_column(
        "client_company_loan",
        sa.Column("calculation_method", sa.String(length=40), server_default="micro_loan", nullable=False),
    )
    op.add_column(
        "client_company_loan",
        sa.Column(
            "calculation_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "loan_offers",
        sa.Column("calculation_method", sa.String(length=40), server_default="micro_loan", nullable=False),
    )
    op.add_column(
        "loan_offers",
        sa.Column(
            "calculation_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.create_table(
        "cash_transactions",
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("handled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", postgresql.ENUM(name="paymentdirection", create_type=False), nullable=False),
        sa.Column("cash_reference", sa.String(length=80), nullable=False),
        sa.Column("tendered_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("applied_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("change_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("forward_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("expected_installment_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("installment_outstanding_before", sa.Numeric(15, 2), nullable=True),
        sa.Column("installment_outstanding_after", sa.Numeric(15, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_cash_transaction_payment"),
        sa.UniqueConstraint("cash_reference", name="uq_cash_transaction_reference"),
    )
    op.create_index("ix_cash_transactions_payment_id", "cash_transactions", ["payment_id"])
    op.create_index("ix_cash_transactions_branch_id", "cash_transactions", ["branch_id"])
    op.create_index("ix_cash_transactions_handled_by_user_id", "cash_transactions", ["handled_by_user_id"])
    op.create_index("ix_cash_transactions_direction", "cash_transactions", ["direction"])
    op.create_index("ix_cash_transactions_cash_reference", "cash_transactions", ["cash_reference"])

    # Cash-only defaults for all editable fee configurations. Historical provider
    # rows and tables remain for audit-safe upgrades but are no longer imported or routed.
    op.execute("UPDATE borrower_fee_configurations SET allowed_providers = '[\"cash\"]'::jsonb")
    op.execute("UPDATE company_account_opening_fee_configurations SET allowed_providers = '[\"cash\"]'::jsonb, required_before_activation = false")


def downgrade() -> None:
    op.drop_index("ix_cash_transactions_cash_reference", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_direction", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_handled_by_user_id", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_branch_id", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_payment_id", table_name="cash_transactions")
    op.drop_table("cash_transactions")
    op.drop_column("loan_offers", "calculation_breakdown")
    op.drop_column("loan_offers", "calculation_method")
    op.drop_column("client_company_loan", "calculation_breakdown")
    op.drop_column("client_company_loan", "calculation_method")
    # Keep the wider loan number column and CASH enum label to avoid destructive
    # downgrade failures after production references and cash records existed.
