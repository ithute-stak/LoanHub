"""Enterprise branch expense and money management.

Revision ID: j9e4b7c2f930
Revises: h7c2a9d4e810
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "j9e4b7c2f930"
down_revision = "h7c2a9d4e810"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "company_branches",
        sa.Column("is_headquarters", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_company_branches_is_headquarters", "company_branches", ["is_headquarters"])

    op.add_column(
        "payment_transactions",
        sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
    )
    op.add_column("payment_transactions", sa.Column("proof_reference", sa.String(length=180), nullable=True))
    op.add_column("payment_transactions", sa.Column("proof_url", sa.String(length=500), nullable=True))
    op.add_column("payment_transactions", sa.Column("proof_notes", sa.Text(), nullable=True))
    op.add_column(
        "payment_transactions",
        sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("payment_transactions", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_payment_transactions_verified_by_user",
        "payment_transactions",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_payment_transactions_payment_method", "payment_transactions", ["payment_method"])
    op.create_index("ix_payment_transactions_proof_reference", "payment_transactions", ["proof_reference"])

    op.create_table(
        "treasury_settings",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("headquarters_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="Africa/Maseru"),
        sa.Column("auto_submit_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_submit_time", sa.Time(), nullable=False, server_default=sa.text("'16:30:00'::time")),
        sa.Column("require_proof_for_non_cash", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_branch_reopen", sa.Boolean(), nullable=False, server_default=sa.false()),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["headquarters_branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_treasury_settings_company"),
    )
    op.create_index("ix_treasury_settings_company_id", "treasury_settings", ["company_id"])
    op.create_index("ix_treasury_settings_headquarters_branch_id", "treasury_settings", ["headquarters_branch_id"])

    op.create_table(
        "expense_categories",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_expense_category_company_name"),
    )
    op.create_index("ix_expense_categories_company_id", "expense_categories", ["company_id"])

    op.create_table(
        "branch_daily_ledgers",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("opening_balance", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("total_money_in", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("total_money_out", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("expected_closing_balance", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("declared_closing_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("variance_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("auto_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "branch_id",
            "business_date",
            name="uq_branch_daily_ledger_company_branch_date",
        ),
    )
    op.create_index("ix_branch_daily_ledgers_company_id", "branch_daily_ledgers", ["company_id"])
    op.create_index("ix_branch_daily_ledgers_branch_id", "branch_daily_ledgers", ["branch_id"])
    op.create_index("ix_branch_daily_ledgers_business_date", "branch_daily_ledgers", ["business_date"])
    op.create_index("ix_branch_daily_ledgers_status", "branch_daily_ledgers", ["status"])

    op.create_table(
        "branch_funding_transfers",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="issued"),
        sa.Column("proof_reference", sa.String(length=180), nullable=True),
        sa.Column("proof_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("received_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_branch_funding_transfer_reference"),
    )
    op.create_index("ix_branch_funding_transfers_company_id", "branch_funding_transfers", ["company_id"])
    op.create_index("ix_branch_funding_transfers_source_branch_id", "branch_funding_transfers", ["source_branch_id"])
    op.create_index("ix_branch_funding_transfers_target_branch_id", "branch_funding_transfers", ["target_branch_id"])
    op.create_index("ix_branch_funding_transfers_business_date", "branch_funding_transfers", ["business_date"])
    op.create_index("ix_branch_funding_transfers_status", "branch_funding_transfers", ["status"])

    op.create_table(
        "treasury_entries",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("proof_reference", sa.String(length=180), nullable=True),
        sa.Column("proof_url", sa.String(length=500), nullable=True),
        sa.Column("proof_notes", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(length=180), nullable=True),
        sa.Column("expense_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("counterparty_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_voided", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_ledger_id"], ["branch_daily_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_category_id"], ["expense_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transfer_id"], ["branch_funding_transfers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["counterparty_branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_transaction_id", name="uq_treasury_entry_payment_transaction"),
    )
    for column in [
        "company_id",
        "branch_id",
        "daily_ledger_id",
        "direction",
        "entry_type",
        "payment_method",
        "occurred_at",
        "proof_reference",
        "external_reference",
        "expense_category_id",
        "payment_transaction_id",
        "loan_id",
        "borrower_id",
        "transfer_id",
        "counterparty_branch_id",
        "recorded_by_user_id",
        "is_voided",
    ]:
        op.create_index(f"ix_treasury_entries_{column}", "treasury_entries", [column])

    op.create_table(
        "branch_daily_submissions",
        sa.Column("daily_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_automatic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opening_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_money_in", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_money_out", sa.Numeric(15, 2), nullable=False),
        sa.Column("closing_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("declared_closing_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("variance_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel_totals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expense_totals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["daily_ledger_id"], ["branch_daily_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_ledger_id", "sequence_number", name="uq_branch_daily_submission_sequence"),
    )
    op.create_index("ix_branch_daily_submissions_daily_ledger_id", "branch_daily_submissions", ["daily_ledger_id"])
    op.create_index("ix_branch_daily_submissions_company_id", "branch_daily_submissions", ["company_id"])
    op.create_index("ix_branch_daily_submissions_branch_id", "branch_daily_submissions", ["branch_id"])
    op.create_index("ix_branch_daily_submissions_business_date", "branch_daily_submissions", ["business_date"])


def downgrade() -> None:
    op.drop_table("branch_daily_submissions")
    op.drop_table("treasury_entries")
    op.drop_table("branch_funding_transfers")
    op.drop_table("branch_daily_ledgers")
    op.drop_table("expense_categories")
    op.drop_table("treasury_settings")

    op.drop_index("ix_payment_transactions_proof_reference", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_payment_method", table_name="payment_transactions")
    op.drop_constraint("fk_payment_transactions_verified_by_user", "payment_transactions", type_="foreignkey")
    op.drop_column("payment_transactions", "verified_at")
    op.drop_column("payment_transactions", "verified_by_user_id")
    op.drop_column("payment_transactions", "proof_notes")
    op.drop_column("payment_transactions", "proof_url")
    op.drop_column("payment_transactions", "proof_reference")
    op.drop_column("payment_transactions", "payment_method")

    op.drop_index("ix_company_branches_is_headquarters", table_name="company_branches")
    op.drop_column("company_branches", "is_headquarters")
