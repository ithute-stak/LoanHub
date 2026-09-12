"""Add auditable legacy cash-out book loan captures.

Revision ID: m3c7e9f1a013
Revises: l2b6d8e0f012
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "m3c7e9f1a013"
down_revision = "l2b6d8e0f012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_loan_captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("captured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_borrower_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("folio_number", sa.String(length=80), nullable=False),
        sa.Column("book_date", sa.Date(), nullable=True),
        sa.Column("surname", sa.String(length=100), nullable=True),
        sa.Column("names", sa.String(length=220), nullable=True),
        sa.Column("passport_number", sa.String(length=100), nullable=True),
        sa.Column("national_id", sa.String(length=100), nullable=True),
        sa.Column("id_expiry_date", sa.Date(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("residential_address", sa.Text(), nullable=True),
        sa.Column("postal_address", sa.Text(), nullable=True),
        sa.Column("employer", sa.String(length=200), nullable=True),
        sa.Column("occupation", sa.String(length=150), nullable=True),
        sa.Column("net_pay", sa.Numeric(15, 2), nullable=True),
        sa.Column("employee_number", sa.String(length=100), nullable=True),
        sa.Column("cell_phone", sa.String(length=30), nullable=True),
        sa.Column("home_phone", sa.String(length=30), nullable=True),
        sa.Column("work_phone", sa.String(length=30), nullable=True),
        sa.Column("next_of_kin_contact", sa.String(length=30), nullable=True),
        sa.Column("next_of_kin_name", sa.String(length=200), nullable=True),
        sa.Column("next_of_kin_relationship", sa.String(length=100), nullable=True),
        sa.Column("borrowed_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("banking_info", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("bank_account_number_encrypted", sa.Text(), nullable=True),
        sa.Column("bank_account_number_last4", sa.String(length=4), nullable=True),
        sa.Column("paper_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("conversion_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["captured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_borrower_account_id"], ["company_borrower_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "folio_number", name="uq_legacy_loan_capture_company_folio"),
        sa.UniqueConstraint("loan_id", name="uq_legacy_loan_captures_loan_id"),
    )
    for column in (
        "company_id", "branch_id", "captured_by_user_id", "borrower_id",
        "company_borrower_account_id", "loan_id", "folio_number", "status",
    ):
        op.create_index(f"ix_legacy_loan_captures_{column}", "legacy_loan_captures", [column])
    op.create_index(
        "ix_legacy_loan_captures_company_status_created",
        "legacy_loan_captures",
        ["company_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_legacy_loan_captures_company_status_created", table_name="legacy_loan_captures")
    for column in reversed((
        "company_id", "branch_id", "captured_by_user_id", "borrower_id",
        "company_borrower_account_id", "loan_id", "folio_number", "status",
    )):
        op.drop_index(f"ix_legacy_loan_captures_{column}", table_name="legacy_loan_captures")
    op.drop_table("legacy_loan_captures")
