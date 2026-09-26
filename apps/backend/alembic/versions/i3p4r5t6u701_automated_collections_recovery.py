"""add automated collections recovery engine

Revision ID: i3p4r5t6u701
Revises: h2n3q4s5t601
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "i3p4r5t6u701"
down_revision = "h2n3q4s5t601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_treatment_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("strategy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_collection_treatment_policy_company_name"),
    )
    op.create_index("ix_collection_treatment_policies_company_id", "collection_treatment_policies", ["company_id"])
    op.create_index("ix_collection_treatment_policies_is_active", "collection_treatment_policies", ["is_active"])

    op.create_table(
        "collection_work_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deduplication_key", sa.String(length=180), nullable=False),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("treatment_code", sa.String(length=80), nullable=False),
        sa.Column("recovery_path", sa.String(length=60), server_default="direct_collection", nullable=False),
        sa.Column("priority_score", sa.Numeric(10, 3), server_default="0", nullable=False),
        sa.Column("priority", sa.String(length=30), server_default="normal", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=40), server_default="automation", nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('open','in_progress','completed','cancelled')", name="ck_collection_work_item_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_collection_work_item_priority"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["collection_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "deduplication_key", name="uq_collection_work_item_case_dedup"),
    )
    for name, columns in (
        ("ix_collection_work_items_company_id", ["company_id"]),
        ("ix_collection_work_items_branch_id", ["branch_id"]),
        ("ix_collection_work_items_case_id", ["case_id"]),
        ("ix_collection_work_items_loan_id", ["loan_id"]),
        ("ix_collection_work_items_borrower_id", ["borrower_id"]),
        ("ix_collection_work_items_assigned_to_user_id", ["assigned_to_user_id"]),
        ("ix_collection_work_items_action_type", ["action_type"]),
        ("ix_collection_work_items_treatment_code", ["treatment_code"]),
        ("ix_collection_work_items_recovery_path", ["recovery_path"]),
        ("ix_collection_work_items_priority_score", ["priority_score"]),
        ("ix_collection_work_items_priority", ["priority"]),
        ("ix_collection_work_items_due_at", ["due_at"]),
        ("ix_collection_work_items_status", ["status"]),
    ):
        op.create_index(name, "collection_work_items", columns)

    op.create_table(
        "collection_automation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("cases_checked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("work_items_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("work_items_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("broken_promises_detected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("legal_ready_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_reference"),
    )
    op.create_index("ix_collection_automation_runs_company_id", "collection_automation_runs", ["company_id"])
    op.create_index("ix_collection_automation_runs_branch_id", "collection_automation_runs", ["branch_id"])
    op.create_index("ix_collection_automation_runs_run_reference", "collection_automation_runs", ["run_reference"])
    op.create_index("ix_collection_automation_runs_status", "collection_automation_runs", ["status"])


def downgrade() -> None:
    op.drop_table("collection_automation_runs")
    op.drop_table("collection_work_items")
    op.drop_table("collection_treatment_policies")
