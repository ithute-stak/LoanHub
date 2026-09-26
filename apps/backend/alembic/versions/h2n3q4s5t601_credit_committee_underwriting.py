"""add credit committee underwriting workflow

Revision ID: h2n3q4s5t601
Revises: g1m2p3r4s502
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "h2n3q4s5t601"
down_revision = "g1m2p3r4s502"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing applications pre-date committee governance and must not be
    # retroactively blocked. New rows use the true server default below.
    op.add_column(
        "direct_loan_applications",
        sa.Column("credit_committee_required", sa.Boolean(), nullable=True),
    )
    op.execute("UPDATE direct_loan_applications SET credit_committee_required = false")
    op.alter_column(
        "direct_loan_applications",
        "credit_committee_required",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    op.create_index(
        "ix_direct_loan_applications_credit_committee_required",
        "direct_loan_applications",
        ["credit_committee_required"],
    )

    op.create_table(
        "credit_committee_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_reference", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="underwriting", nullable=False),
        sa.Column("required_votes", sa.Integer(), server_default="2", nullable=False),
        sa.Column("approval_threshold_percent", sa.Numeric(6, 3), server_default="66.667", nullable=False),
        sa.Column("maker_checker_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("analyst_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analyst_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("final_decision", sa.String(length=40), nullable=True),
        sa.Column("final_decision_reason", sa.Text(), nullable=True),
        sa.Column("final_decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("final_decided_at", sa.DateTime(), nullable=True),
        sa.Column("final_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("override_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("required_votes >= 1 AND required_votes <= 20", name="ck_credit_committee_case_required_votes"),
        sa.CheckConstraint("approval_threshold_percent > 0 AND approval_threshold_percent <= 100", name="ck_credit_committee_case_threshold"),
        sa.CheckConstraint("status IN ('underwriting','committee_review','awaiting_conditions','approved','rejected','cancelled')", name="ck_credit_committee_case_status"),
        sa.CheckConstraint("final_decision IS NULL OR final_decision IN ('approved','conditionally_approved','rejected')", name="ck_credit_committee_case_final_decision"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["application_id"], ["direct_loan_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["analyst_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["final_decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "application_id", name="uq_credit_committee_case_company_application"),
        sa.UniqueConstraint("case_reference"),
    )
    for column in ("company_id", "branch_id", "application_id", "borrower_id", "case_reference", "status", "analyst_user_id", "final_decision"):
        op.create_index(f"ix_credit_committee_cases_{column}", "credit_committee_cases", [column])

    op.create_table(
        "underwriting_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="submitted", nullable=False),
        sa.Column("analyst_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("proposed_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("proposed_installment", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("proposed_term", sa.Integer(), server_default="0", nullable=False),
        sa.Column("verified_income", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("household_expenses", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("existing_debt_installments", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("dti_percent", sa.Numeric(8, 3), server_default="0", nullable=False),
        sa.Column("affordability_headroom", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("bureau_score", sa.Integer(), nullable=True),
        sa.Column("bureau_risk_grade", sa.String(length=40), nullable=True),
        sa.Column("kyc_status", sa.String(length=40), nullable=True),
        sa.Column("risk_score", sa.Numeric(8, 3), nullable=True),
        sa.Column("risk_grade", sa.String(length=30), server_default="medium", nullable=False),
        sa.Column("recommendation", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("exceptions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("mitigants", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("proposed_conditions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_underwriting_assessment_revision"),
        sa.CheckConstraint("status IN ('submitted','superseded')", name="ck_underwriting_assessment_status"),
        sa.CheckConstraint("risk_grade IN ('low','medium','high','critical')", name="ck_underwriting_assessment_risk_grade"),
        sa.CheckConstraint("recommendation IN ('approve','approve_with_conditions','reject','refer')", name="ck_underwriting_assessment_recommendation"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["credit_committee_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["direct_loan_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["analyst_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "revision", name="uq_underwriting_assessment_case_revision"),
    )
    for column in ("company_id", "case_id", "application_id", "borrower_id", "status", "analyst_user_id", "risk_grade", "recommendation"):
        op.create_index(f"ix_underwriting_assessments_{column}", "underwriting_assessments", [column])

    op.create_table(
        "credit_committee_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("voted_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("decision IN ('approve','approve_with_conditions','reject','abstain')", name="ck_credit_committee_vote_decision"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["credit_committee_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_credit_committee_vote_case_user"),
    )
    for column in ("company_id", "case_id", "user_id", "decision"):
        op.create_index(f"ix_credit_committee_votes_{column}", "credit_committee_votes", [column])

    op.create_table(
        "credit_committee_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=40), server_default="committee", nullable=False),
        sa.Column("condition_type", sa.String(length=40), server_default="pre_disbursement", nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("condition_type IN ('pre_contract','pre_disbursement','monitoring')", name="ck_credit_committee_condition_type"),
        sa.CheckConstraint("status IN ('open','satisfied','waived','failed')", name="ck_credit_committee_condition_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["credit_committee_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "case_id", "condition_type", "status"):
        op.create_index(f"ix_credit_committee_conditions_{column}", "credit_committee_conditions", [column])

    op.create_table(
        "credit_committee_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["credit_committee_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "case_id", "event_type", "actor_user_id"):
        op.create_index(f"ix_credit_committee_events_{column}", "credit_committee_events", [column])


def downgrade() -> None:
    op.drop_table("credit_committee_events")
    op.drop_table("credit_committee_conditions")
    op.drop_table("credit_committee_votes")
    op.drop_table("underwriting_assessments")
    op.drop_table("credit_committee_cases")
    op.drop_index("ix_direct_loan_applications_credit_committee_required", table_name="direct_loan_applications")
    op.drop_column("direct_loan_applications", "credit_committee_required")
