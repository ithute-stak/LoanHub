"""Add platform credit bureau PAYG subscriptions and transaction ledger.

Revision ID: a8c2e4f6g810
Revises: 7d2e4f6a8b10
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8c2e4f6g810"
down_revision = "7d2e4f6a8b10"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "platform_credit_bureau_subscriptions",
        *_audit_columns(),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="experian"),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("price_per_transaction", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "company_id", name="uq_credit_bureau_subscription_provider_company"),
    )
    op.create_index("ix_platform_credit_bureau_subscriptions_provider", "platform_credit_bureau_subscriptions", ["provider"])
    op.create_index("ix_platform_credit_bureau_subscriptions_company_id", "platform_credit_bureau_subscriptions", ["company_id"])
    op.create_index("ix_platform_credit_bureau_subscriptions_status", "platform_credit_bureau_subscriptions", ["status"])

    op.create_table(
        "platform_credit_bureau_transactions",
        *_audit_columns(),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="experian"),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enquiry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_reference", sa.String(length=100), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="accrued"),
        sa.Column("accrued_at", sa.DateTime(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("waived_at", sa.DateTime(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["platform_credit_bureau_subscriptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enquiry_id"], ["credit_bureau_enquiries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enquiry_id", name="uq_credit_bureau_payg_enquiry"),
        sa.UniqueConstraint("transaction_reference"),
    )
    op.create_index("ix_platform_credit_bureau_transactions_provider", "platform_credit_bureau_transactions", ["provider"])
    op.create_index("ix_platform_credit_bureau_transactions_company_id", "platform_credit_bureau_transactions", ["company_id"])
    op.create_index("ix_platform_credit_bureau_transactions_subscription_id", "platform_credit_bureau_transactions", ["subscription_id"])
    op.create_index("ix_platform_credit_bureau_transactions_enquiry_id", "platform_credit_bureau_transactions", ["enquiry_id"])
    op.create_index("ix_platform_credit_bureau_transactions_transaction_reference", "platform_credit_bureau_transactions", ["transaction_reference"], unique=True)
    op.create_index("ix_platform_credit_bureau_transactions_status", "platform_credit_bureau_transactions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_platform_credit_bureau_transactions_status", table_name="platform_credit_bureau_transactions")
    op.drop_index("ix_platform_credit_bureau_transactions_transaction_reference", table_name="platform_credit_bureau_transactions")
    op.drop_index("ix_platform_credit_bureau_transactions_enquiry_id", table_name="platform_credit_bureau_transactions")
    op.drop_index("ix_platform_credit_bureau_transactions_subscription_id", table_name="platform_credit_bureau_transactions")
    op.drop_index("ix_platform_credit_bureau_transactions_company_id", table_name="platform_credit_bureau_transactions")
    op.drop_index("ix_platform_credit_bureau_transactions_provider", table_name="platform_credit_bureau_transactions")
    op.drop_table("platform_credit_bureau_transactions")

    op.drop_index("ix_platform_credit_bureau_subscriptions_status", table_name="platform_credit_bureau_subscriptions")
    op.drop_index("ix_platform_credit_bureau_subscriptions_company_id", table_name="platform_credit_bureau_subscriptions")
    op.drop_index("ix_platform_credit_bureau_subscriptions_provider", table_name="platform_credit_bureau_subscriptions")
    op.drop_table("platform_credit_bureau_subscriptions")
