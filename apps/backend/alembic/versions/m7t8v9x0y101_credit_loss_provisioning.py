"""add credit loss provisioning

Revision ID: m7t8v9x0y101
Revises: l6s7u8w9x001
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m7t8v9x0y101"
down_revision = "l6s7u8w9x001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_loss_provision_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("rates", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", "version", name="uq_credit_loss_policy_version"),
    )
    op.create_index("ix_credit_loss_provision_policies_company_id", "credit_loss_provision_policies", ["company_id"])
    op.create_index("ix_credit_loss_provision_policies_status", "credit_loss_provision_policies", ["status"])

    op.create_table(
        "credit_loss_provision_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_scope_key", sa.String(length=40), server_default="ALL", nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("loan_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("gross_exposure", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("required_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("prior_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("allowance_movement", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("stage_1_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("stage_2_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("stage_3_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("management_overlay", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("overlay_reason", sa.Text(), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft','approved','posted','superseded')", name="ck_credit_loss_run_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["credit_loss_provision_policies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "as_of_date", "branch_scope_key", name="uq_credit_loss_run_scope_date"),
        sa.UniqueConstraint("run_reference", name="uq_credit_loss_run_reference"),
    )
    for column in ("company_id", "branch_id", "branch_scope_key", "policy_id", "run_reference", "as_of_date", "status", "journal_entry_id"):
        op.create_index(f"ix_credit_loss_provision_runs_{column}", "credit_loss_provision_runs", [column])

    op.create_table(
        "credit_loss_provision_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_number", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("days_past_due", sa.Integer(), server_default="0", nullable=False),
        sa.Column("exposure", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("provision_rate", sa.Numeric(8, 4), server_default="0", nullable=False),
        sa.Column("base_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("overlay_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("required_allowance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("rationale", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("write_off_candidate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("stage IN (1,2,3)", name="ck_credit_loss_line_stage"),
        sa.CheckConstraint("provision_rate >= 0 AND provision_rate <= 1", name="ck_credit_loss_line_rate"),
        sa.ForeignKeyConstraint(["run_id"], ["credit_loss_provision_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "loan_id", name="uq_credit_loss_line_run_loan"),
    )
    for column in ("run_id", "company_id", "branch_id", "loan_id", "borrower_id", "folio_number", "stage", "write_off_candidate"):
        op.create_index(f"ix_credit_loss_provision_lines_{column}", "credit_loss_provision_lines", [column])


def downgrade() -> None:
    op.drop_table("credit_loss_provision_lines")
    op.drop_table("credit_loss_provision_runs")
    op.drop_table("credit_loss_provision_policies")
