"""DBMS-book workload indexes and integrity guards.

Revision ID: d1f5h7j9k123
Revises: c0e4g6h8j012
Create Date: 2026-10-05

This migration applies workload-driven physical design and integrity principles:
- composite/partial indexes for real multi-column query predicates
- NOT VALID CHECK constraints so new writes are protected immediately while
  legacy rows can be audited before validation
"""

from alembic import op


revision = "d1f5h7j9k123"
down_revision = "c0e4g6h8j012"
branch_labels = None
depends_on = None


INDEX_SQL = (
    """
    CREATE INDEX IF NOT EXISTS ix_credit_bureau_enquiries_latest_experian_app
    ON credit_bureau_enquiries
        (company_id, application_id, borrower_id, completed_at DESC, requested_at DESC)
    WHERE provider = 'experian'
      AND status = 'completed'
      AND completed_at IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_platform_cb_tx_outstanding
    ON platform_credit_bureau_transactions (company_id, status)
    WHERE provider = 'experian'
      AND status IN ('reserved', 'accrued', 'invoiced')
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_platform_cb_tx_company_accrued
    ON platform_credit_bureau_transactions (company_id, accrued_at DESC, status)
    WHERE provider = 'experian'
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_platform_cb_tx_stale_reservations
    ON platform_credit_bureau_transactions (accrued_at, enquiry_id)
    WHERE provider = 'experian'
      AND status = 'reserved'
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_platform_cb_invoice_overdue
    ON platform_credit_bureau_invoices (due_at, company_id)
    WHERE provider = 'experian'
      AND status = 'issued'
      AND amount_due > 0
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_platform_cb_invoice_company_issued
    ON platform_credit_bureau_invoices (company_id, issued_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cdas_mandates_company_loan
    ON cdas_deduction_mandates (company_id, loan_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_credit_committee_conditions_gate
    ON credit_committee_conditions (case_id, condition_type, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_credit_committee_cases_company_created
    ON credit_committee_cases (company_id, created_at DESC)
    """,
)


CONSTRAINT_SQL = (
    """
    ALTER TABLE platform_credit_bureau_subscriptions
    ADD CONSTRAINT ck_platform_cb_subscription_financial_terms
    CHECK (
        price_per_transaction >= 0
        AND (credit_limit IS NULL OR credit_limit >= 0)
        AND (warning_threshold IS NULL OR warning_threshold >= 0)
        AND billing_due_days BETWEEN 1 AND 90
    ) NOT VALID
    """,
    """
    ALTER TABLE platform_credit_bureau_transactions
    ADD CONSTRAINT ck_platform_cb_transaction_nonnegative_amounts
    CHECK (unit_price >= 0 AND amount >= 0) NOT VALID
    """,
    """
    ALTER TABLE platform_credit_bureau_invoices
    ADD CONSTRAINT ck_platform_cb_invoice_financial_integrity
    CHECK (
        transaction_count >= 0
        AND subtotal >= 0
        AND waived_amount >= 0
        AND amount_due >= 0
        AND period_end >= period_start
    ) NOT VALID
    """,
    """
    ALTER TABLE cdas_payroll_profiles
    ADD CONSTRAINT ck_cdas_payroll_financial_integrity
    CHECK (
        gross_salary >= 0
        AND net_salary >= 0
        AND existing_deductions >= 0
        AND maximum_deduction_percent >= 0
        AND maximum_deduction_percent <= 100
    ) NOT VALID
    """,
    """
    ALTER TABLE cdas_deduction_mandates
    ADD CONSTRAINT ck_cdas_mandate_financial_integrity
    CHECK (
        monthly_deduction >= 0
        AND expected_installments >= 1
        AND deductions_received >= 0
        AND total_expected >= 0
        AND total_received >= 0
        AND (end_date IS NULL OR end_date >= start_date)
    ) NOT VALID
    """,
)


def upgrade() -> None:
    for statement in INDEX_SQL:
        op.execute(statement)
    for statement in CONSTRAINT_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE cdas_deduction_mandates DROP CONSTRAINT IF EXISTS ck_cdas_mandate_financial_integrity")
    op.execute("ALTER TABLE cdas_payroll_profiles DROP CONSTRAINT IF EXISTS ck_cdas_payroll_financial_integrity")
    op.execute("ALTER TABLE platform_credit_bureau_invoices DROP CONSTRAINT IF EXISTS ck_platform_cb_invoice_financial_integrity")
    op.execute("ALTER TABLE platform_credit_bureau_transactions DROP CONSTRAINT IF EXISTS ck_platform_cb_transaction_nonnegative_amounts")
    op.execute("ALTER TABLE platform_credit_bureau_subscriptions DROP CONSTRAINT IF EXISTS ck_platform_cb_subscription_financial_terms")

    op.execute("DROP INDEX IF EXISTS ix_credit_committee_cases_company_created")
    op.execute("DROP INDEX IF EXISTS ix_credit_committee_conditions_gate")
    op.execute("DROP INDEX IF EXISTS ix_cdas_mandates_company_loan")
    op.execute("DROP INDEX IF EXISTS ix_platform_cb_invoice_company_issued")
    op.execute("DROP INDEX IF EXISTS ix_platform_cb_invoice_overdue")
    op.execute("DROP INDEX IF EXISTS ix_platform_cb_tx_stale_reservations")
    op.execute("DROP INDEX IF EXISTS ix_platform_cb_tx_company_accrued")
    op.execute("DROP INDEX IF EXISTS ix_platform_cb_tx_outstanding")
    op.execute("DROP INDEX IF EXISTS ix_credit_bureau_enquiries_latest_experian_app")
