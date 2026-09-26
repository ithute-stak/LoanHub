"""add employer payroll management centre

Revision ID: g1m2p3r4s501
Revises: f0l10a5e0001
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "g1m2p3r4s501"
down_revision = "f0l10a5e0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_payroll_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employer_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_reference", sa.String(length=100), nullable=True),
        sa.Column("payroll_day", sa.Integer(), nullable=True),
        sa.Column("collection_channel", sa.String(length=40), server_default="employer_payroll", nullable=False),
        sa.Column("reconciliation_tolerance", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("payroll_contact_name", sa.String(length=200), nullable=True),
        sa.Column("payroll_contact_email", sa.String(length=255), nullable=True),
        sa.Column("payroll_contact_phone", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint("payroll_day IS NULL OR (payroll_day >= 1 AND payroll_day <= 31)", name="ck_employer_payroll_account_payroll_day"),
        sa.CheckConstraint("reconciliation_tolerance >= 0", name="ck_employer_payroll_account_tolerance"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employer_group_id"], ["employer_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employer_group_id", name="uq_employer_payroll_account_company_group"),
    )
    op.create_index("ix_employer_payroll_accounts_company_id", "employer_payroll_accounts", ["company_id"])
    op.create_index("ix_employer_payroll_accounts_branch_id", "employer_payroll_accounts", ["branch_id"])
    op.create_index("ix_employer_payroll_accounts_employer_group_id", "employer_payroll_accounts", ["employer_group_id"])
    op.create_index("ix_employer_payroll_accounts_payroll_reference", "employer_payroll_accounts", ["payroll_reference"])
    op.create_index("ix_employer_payroll_accounts_collection_channel", "employer_payroll_accounts", ["collection_channel"])
    op.create_index("ix_employer_payroll_accounts_is_active", "employer_payroll_accounts", ["is_active"])

    op.create_table(
        "employer_payroll_employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employer_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_number", sa.String(length=100), nullable=True),
        sa.Column("employment_state", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("employment_state IN ('active','suspended','terminated','left_employer')", name="ck_employer_payroll_employee_state"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employer_account_id"], ["employer_payroll_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employer_account_id", "borrower_id", name="uq_employer_payroll_employee_company_account_borrower"),
        sa.UniqueConstraint("employer_account_id", "employee_number", name="uq_employer_payroll_employee_account_number"),
    )
    op.create_index("ix_employer_payroll_employees_company_id", "employer_payroll_employees", ["company_id"])
    op.create_index("ix_employer_payroll_employees_employer_account_id", "employer_payroll_employees", ["employer_account_id"])
    op.create_index("ix_employer_payroll_employees_borrower_id", "employer_payroll_employees", ["borrower_id"])
    op.create_index("ix_employer_payroll_employees_employee_number", "employer_payroll_employees", ["employee_number"])
    op.create_index("ix_employer_payroll_employees_employment_state", "employer_payroll_employees", ["employment_state"])
    op.create_index("ix_employer_payroll_employees_termination_date", "employer_payroll_employees", ["termination_date"])

    op.create_table(
        "employer_payroll_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employer_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("scheduled_pay_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("actual_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("shortage_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("excess_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("rejected_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("expected_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("exception_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("source", sa.String(length=40), server_default="loanhub", nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('draft','open','received','reconciled','exception')", name="ck_employer_payroll_cycle_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employer_account_id"], ["employer_payroll_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employer_account_id", "period_key", name="uq_employer_payroll_cycle_company_account_period"),
    )
    op.create_index("ix_employer_payroll_cycles_company_id", "employer_payroll_cycles", ["company_id"])
    op.create_index("ix_employer_payroll_cycles_employer_account_id", "employer_payroll_cycles", ["employer_account_id"])
    op.create_index("ix_employer_payroll_cycles_branch_id", "employer_payroll_cycles", ["branch_id"])
    op.create_index("ix_employer_payroll_cycles_period_key", "employer_payroll_cycles", ["period_key"])
    op.create_index("ix_employer_payroll_cycles_scheduled_pay_date", "employer_payroll_cycles", ["scheduled_pay_date"])
    op.create_index("ix_employer_payroll_cycles_status", "employer_payroll_cycles", ["status"])

    op.create_table(
        "employer_payroll_deductions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("folio_number", sa.String(length=40), nullable=True),
        sa.Column("employee_number", sa.String(length=100), nullable=True),
        sa.Column("source_line_key", sa.String(length=160), nullable=False),
        sa.Column("expected_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("actual_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("variance_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("rejection_code", sa.String(length=80), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("employer_reference", sa.String(length=180), nullable=True),
        sa.Column("source_row", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending','matched','shortage','excess','rejected','missing','terminated','unmatched')", name="ck_employer_payroll_deduction_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["employer_payroll_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "source_line_key", name="uq_employer_payroll_deduction_cycle_source_key"),
    )
    op.create_index("ix_employer_payroll_deductions_company_id", "employer_payroll_deductions", ["company_id"])
    op.create_index("ix_employer_payroll_deductions_cycle_id", "employer_payroll_deductions", ["cycle_id"])
    op.create_index("ix_employer_payroll_deductions_borrower_id", "employer_payroll_deductions", ["borrower_id"])
    op.create_index("ix_employer_payroll_deductions_loan_id", "employer_payroll_deductions", ["loan_id"])
    op.create_index("ix_employer_payroll_deductions_folio_number", "employer_payroll_deductions", ["folio_number"])
    op.create_index("ix_employer_payroll_deductions_employee_number", "employer_payroll_deductions", ["employee_number"])
    op.create_index("ix_employer_payroll_deductions_status", "employer_payroll_deductions", ["status"])


def downgrade() -> None:
    op.drop_table("employer_payroll_deductions")
    op.drop_table("employer_payroll_cycles")
    op.drop_table("employer_payroll_employees")
    op.drop_table("employer_payroll_accounts")
