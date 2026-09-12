"""Real-world daily treasury controls and configurable loan top-ups.

Revision ID: k3f1a6b8c240
Revises: j9e4b7c2f930
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "k3f1a6b8c240"
down_revision = "j9e4b7c2f930"
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
    # Daily-cycle and approval policy.
    op.add_column("treasury_settings", sa.Column("auto_open_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("treasury_settings", sa.Column("auto_open_time", sa.Time(), nullable=False, server_default=sa.text("'00:01:00'::time")))
    op.add_column("treasury_settings", sa.Column("expense_approval_threshold", sa.Numeric(15, 2), nullable=False, server_default="0"))
    op.add_column("treasury_settings", sa.Column("dual_control_expenses", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("branch_daily_ledgers", sa.Column("pending_entry_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "branch_opening_sources",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(length=180), nullable=False),
        sa.Column("proof_reference", sa.String(length=180), nullable=True),
        sa.Column("proof_url", sa.String(length=500), nullable=True),
        sa.Column("proof_notes", sa.Text(), nullable=True),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_system_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_voided", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_ledger_id"], ["branch_daily_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transfer_id"], ["branch_funding_transfers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_ledger_id", "source_type", "source_reference", name="uq_branch_opening_source_reference"),
    )
    for col in ["company_id", "branch_id", "daily_ledger_id", "source_type", "payment_method", "source_reference", "transfer_id", "is_confirmed", "is_voided"]:
        op.create_index(f"ix_branch_opening_sources_{col}", "branch_opening_sources", [col])

    # Preserve opening figures already present before this release.
    op.execute(sa.text("""
        INSERT INTO branch_opening_sources (
            id, company_id, branch_id, daily_ledger_id, source_type, payment_method,
            amount, currency, description, source_reference, is_system_generated,
            is_confirmed, confirmed_at, is_voided, created_at, updated_at
        )
        SELECT
            md5(random()::text || clock_timestamp()::text || l.id::text)::uuid,
            l.company_id, l.branch_id, l.id, 'previous_closing', 'cash',
            l.opening_balance, 'LSL', 'Opening balance carried into this ledger before source-level tracking',
            'legacy-opening-' || l.id::text, true, true, now(), false, now(), now()
        FROM branch_daily_ledgers l
        WHERE l.opening_balance <> 0
          AND NOT EXISTS (
              SELECT 1 FROM branch_opening_sources s WHERE s.daily_ledger_id = l.id
          )
    """))

    # Expense approval, duplicate-click protection and voucher audit.
    op.add_column("treasury_entries", sa.Column("approval_status", sa.String(length=20), nullable=False, server_default="posted"))
    op.add_column("treasury_entries", sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("treasury_entries", sa.Column("idempotency_key", sa.String(length=180), nullable=True))
    op.add_column("treasury_entries", sa.Column("voucher_number", sa.String(length=100), nullable=True))
    op.add_column("treasury_entries", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("treasury_entries", sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("treasury_entries", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column("treasury_entries", sa.Column("rejected_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("treasury_entries", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_foreign_key("fk_treasury_entries_approved_by", "treasury_entries", "users", ["approved_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_treasury_entries_rejected_by", "treasury_entries", "users", ["rejected_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_treasury_entry_company_idempotency", "treasury_entries", ["company_id", "idempotency_key"])
    for col in ["approval_status", "requires_approval", "idempotency_key", "voucher_number"]:
        op.create_index(f"ix_treasury_entries_{col}", "treasury_entries", [col])

    op.add_column("branch_daily_submissions", sa.Column("submitted_to_branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("branch_daily_submissions", sa.Column("pending_entry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("branch_daily_submissions", sa.Column("opening_source_totals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_foreign_key("fk_branch_submission_headquarters", "branch_daily_submissions", "company_branches", ["submitted_to_branch_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_branch_daily_submissions_submitted_to_branch_id", "branch_daily_submissions", ["submitted_to_branch_id"])

    # Configurable top-up policy and explicit exception governance.
    for name, column in [
        ("top_up_min_paid_percent", sa.Column("top_up_min_paid_percent", sa.Numeric(8, 3), nullable=False, server_default="75")),
        ("top_up_min_paid_installments", sa.Column("top_up_min_paid_installments", sa.Integer(), nullable=False, server_default="0")),
        ("top_up_owner_exception_enabled", sa.Column("top_up_owner_exception_enabled", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("top_up_require_positive_history", sa.Column("top_up_require_positive_history", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("top_up_settle_existing_balance", sa.Column("top_up_settle_existing_balance", sa.Boolean(), nullable=False, server_default=sa.true())),
    ]:
        op.add_column("origination_policies", column)

    op.add_column("direct_loan_applications", sa.Column("application_type", sa.String(length=30), nullable=False, server_default="new_loan"))
    op.add_column("direct_loan_applications", sa.Column("parent_loan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_cash_requested", sa.Numeric(15, 2), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_settlement_amount", sa.Numeric(15, 2), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_cash_to_borrower", sa.Numeric(15, 2), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_eligibility_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("direct_loan_applications", sa.Column("top_up_exception_requested", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("direct_loan_applications", sa.Column("top_up_exception_reason", sa.Text(), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_exception_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("direct_loan_applications", sa.Column("top_up_exception_approved_at", sa.DateTime(), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("top_up_exception_approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_direct_application_parent_loan", "direct_loan_applications", "client_company_loan", ["parent_loan_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_direct_application_topup_exception_user", "direct_loan_applications", "users", ["top_up_exception_approved_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_direct_loan_applications_application_type", "direct_loan_applications", ["application_type"])
    op.create_index("ix_direct_loan_applications_parent_loan_id", "direct_loan_applications", ["parent_loan_id"])

    op.add_column("client_company_loan", sa.Column("is_top_up", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("client_company_loan", sa.Column("parent_loan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("client_company_loan", sa.Column("top_up_settlement_amount", sa.Numeric(15, 2), nullable=False, server_default="0"))
    op.add_column("client_company_loan", sa.Column("top_up_cash_amount", sa.Numeric(15, 2), nullable=False, server_default="0"))
    op.create_foreign_key("fk_client_company_loan_parent", "client_company_loan", "client_company_loan", ["parent_loan_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_client_company_loan_is_top_up", "client_company_loan", ["is_top_up"])
    op.create_index("ix_client_company_loan_parent_loan_id", "client_company_loan", ["parent_loan_id"])

    op.create_table(
        "loan_top_up_settlements",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("settlement_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("cash_to_borrower", sa.Numeric(15, 2), nullable=False),
        sa.Column("parent_balance_before", sa.Numeric(15, 2), nullable=False),
        sa.Column("parent_amount_paid_before", sa.Numeric(15, 2), nullable=False),
        sa.Column("parent_status_before", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="settled"),
        sa.Column("settled_at", sa.DateTime(), nullable=False),
        sa.Column("settled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("reversed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_loan_id"], ["client_company_loan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["settled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("new_loan_id", name="uq_top_up_settlement_new_loan"),
    )
    for col in ["company_id", "borrower_id", "parent_loan_id", "new_loan_id", "status"]:
        op.create_index(f"ix_loan_top_up_settlements_{col}", "loan_top_up_settlements", [col])

    # Correct legacy channel spelling while preserving old records.
    for table in ["payment_transactions", "treasury_entries", "branch_funding_transfers"]:
        op.execute(sa.text(f"UPDATE {table} SET payment_method = 'swipped' WHERE payment_method = 'swiiped'"))


def downgrade() -> None:
    for table in ["payment_transactions", "treasury_entries", "branch_funding_transfers"]:
        op.execute(sa.text(f"UPDATE {table} SET payment_method = 'swiiped' WHERE payment_method = 'swipped'"))

    op.drop_table("loan_top_up_settlements")
    op.drop_index("ix_client_company_loan_parent_loan_id", table_name="client_company_loan")
    op.drop_index("ix_client_company_loan_is_top_up", table_name="client_company_loan")
    op.drop_constraint("fk_client_company_loan_parent", "client_company_loan", type_="foreignkey")
    for col in ["top_up_cash_amount", "top_up_settlement_amount", "parent_loan_id", "is_top_up"]:
        op.drop_column("client_company_loan", col)

    op.drop_index("ix_direct_loan_applications_parent_loan_id", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_application_type", table_name="direct_loan_applications")
    op.drop_constraint("fk_direct_application_topup_exception_user", "direct_loan_applications", type_="foreignkey")
    op.drop_constraint("fk_direct_application_parent_loan", "direct_loan_applications", type_="foreignkey")
    for col in [
        "top_up_exception_approved_by_user_id", "top_up_exception_approved_at", "top_up_exception_approved",
        "top_up_exception_reason", "top_up_exception_requested", "top_up_eligibility_snapshot",
        "top_up_cash_to_borrower", "top_up_settlement_amount", "top_up_cash_requested",
        "parent_loan_id", "application_type",
    ]:
        op.drop_column("direct_loan_applications", col)

    for col in ["top_up_settle_existing_balance", "top_up_require_positive_history", "top_up_owner_exception_enabled", "top_up_min_paid_installments", "top_up_min_paid_percent"]:
        op.drop_column("origination_policies", col)

    op.drop_index("ix_branch_daily_submissions_submitted_to_branch_id", table_name="branch_daily_submissions")
    op.drop_constraint("fk_branch_submission_headquarters", "branch_daily_submissions", type_="foreignkey")
    op.drop_column("branch_daily_submissions", "opening_source_totals")
    op.drop_column("branch_daily_submissions", "pending_entry_count")
    op.drop_column("branch_daily_submissions", "submitted_to_branch_id")

    for col in ["voucher_number", "idempotency_key", "requires_approval", "approval_status"]:
        op.drop_index(f"ix_treasury_entries_{col}", table_name="treasury_entries")
    op.drop_constraint("uq_treasury_entry_company_idempotency", "treasury_entries", type_="unique")
    op.drop_constraint("fk_treasury_entries_rejected_by", "treasury_entries", type_="foreignkey")
    op.drop_constraint("fk_treasury_entries_approved_by", "treasury_entries", type_="foreignkey")
    for col in ["rejection_reason", "rejected_by_user_id", "rejected_at", "approved_by_user_id", "approved_at", "voucher_number", "idempotency_key", "requires_approval", "approval_status"]:
        op.drop_column("treasury_entries", col)

    op.drop_table("branch_opening_sources")
    op.drop_column("branch_daily_ledgers", "pending_entry_count")
    op.drop_column("treasury_settings", "dual_control_expenses")
    op.drop_column("treasury_settings", "expense_approval_threshold")
    op.drop_column("treasury_settings", "auto_open_time")
    op.drop_column("treasury_settings", "auto_open_enabled")
