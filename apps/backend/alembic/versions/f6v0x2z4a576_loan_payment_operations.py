"""loan payment mandates, reminders, restructuring and accounting exports

Revision ID: f6v0x2z4a576
Revises: e4t8v0x2y355
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6v0x2z4a576"
down_revision: Union[str, Sequence[str], None] = "e4t8v0x2y355"
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
    op.create_table(
        "online_repayment_mandates",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gateway_mandate_id", sa.String(80), nullable=True), sa.Column("provider", sa.String(30), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(15,2), nullable=False), sa.Column("frequency", sa.String(30), nullable=False), sa.Column("next_debit_date", sa.Date(), nullable=True), sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("max_debits", sa.Integer(), nullable=True), sa.Column("debits_completed", sa.Integer(), server_default="0", nullable=False), sa.Column("consent_reference", sa.String(160), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=False), sa.Column("revoked_at", sa.DateTime(), nullable=True), sa.Column("failure_reason", sa.Text(), nullable=True), sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        *audit_columns(), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["borrower_id"],["borrowers.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["loan_id"],["client_company_loan.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("gateway_mandate_id"),
    )
    op.create_table(
        "borrower_reminder_preferences",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("sms_enabled", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("email_enabled", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("whatsapp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("days_before_due", sa.Integer(), server_default="3", nullable=False), sa.Column("remind_on_due_date", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("overdue_interval_days", sa.Integer(), server_default="3", nullable=False), sa.Column("payment_link_enabled", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("timezone", sa.String(80), server_default="Africa/Maseru", nullable=False),
        *audit_columns(), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["borrower_id"],["borrowers.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("company_id","borrower_id",name="uq_borrower_reminder_company"),
    )
    op.create_table(
        "repayment_reminders",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("installment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(30), nullable=False), sa.Column("reminder_type", sa.String(40), nullable=False), sa.Column("scheduled_for", sa.DateTime(), nullable=False), sa.Column("status", sa.String(40), nullable=False), sa.Column("deduplication_key", sa.String(255), nullable=False),
        sa.Column("destination_masked", sa.String(120), nullable=True), sa.Column("message", sa.Text(), nullable=False), sa.Column("sent_at", sa.DateTime(), nullable=True), sa.Column("failure_reason", sa.Text(), nullable=True), sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        *audit_columns(), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["borrower_id"],["borrowers.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["loan_id"],["client_company_loan.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["installment_id"],["repayment_installments.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("deduplication_key"),
    )
    op.create_table(
        "loan_restructure_requests",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_term_months", sa.Integer(), nullable=False), sa.Column("approved_rate_percent", sa.Numeric(8,3), nullable=True), sa.Column("payment_holiday_days", sa.Integer(), server_default="0", nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("borrower_accepted", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("approved_at", sa.DateTime(), nullable=True), sa.Column("applied_at", sa.DateTime(), nullable=True), sa.Column("agreement_reference", sa.String(160), nullable=True),
        sa.Column("original_snapshot", postgresql.JSONB(), nullable=False), sa.Column("preview", postgresql.JSONB(), nullable=False), sa.Column("rejection_reason", sa.Text(), nullable=True),
        *audit_columns(), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["borrower_id"],["borrowers.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["loan_id"],["client_company_loan.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["requested_by_user_id"],["users.id"],ondelete="SET NULL"), sa.ForeignKeyConstraint(["approved_by_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("agreement_reference"),
    )
    op.create_table(
        "accounting_exports",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False), sa.Column("format", sa.String(20), nullable=False), sa.Column("destination", sa.String(60), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("entry_count", sa.Integer(), server_default="0", nullable=False), sa.Column("total_debit", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("total_credit", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("generated_at", sa.DateTime(), nullable=False), sa.Column("delivered_at", sa.DateTime(), nullable=True), sa.Column("failure_reason", sa.Text(), nullable=True),
        *audit_columns(), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["generated_by_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    for table, columns in {
        "online_repayment_mandates":["company_id","borrower_id","loan_id","status","next_debit_date"],
        "repayment_reminders":["company_id","borrower_id","loan_id","status","scheduled_for"],
        "loan_restructure_requests":["company_id","borrower_id","loan_id","status"],
        "accounting_exports":["company_id","period_start","period_end","status"],
    }.items():
        for column in columns: op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in ["accounting_exports","loan_restructure_requests","repayment_reminders","borrower_reminder_preferences","online_repayment_mandates"]:
        op.drop_table(table)
