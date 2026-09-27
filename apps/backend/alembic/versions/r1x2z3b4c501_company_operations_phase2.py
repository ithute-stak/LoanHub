"""add specialised company operations phase two

Revision ID: r1x2z3b4c501
Revises: q0w1y2a3b401
Create Date: 2026-09-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r1x2z3b4c501"
down_revision = "q0w1y2a3b401"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table("procurement_vendors", *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("vendor_code", sa.String(80), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False), sa.Column("registration_number", sa.String(120)), sa.Column("tax_number", sa.String(120)),
        sa.Column("contact_name", sa.String(180)), sa.Column("contact_email", sa.String(240)), sa.Column("contact_phone", sa.String(80)), sa.Column("category", sa.String(100)),
        sa.Column("status", sa.String(30), server_default="active", nullable=False), sa.Column("risk_rating", sa.String(30)),
        sa.Column("due_diligence_completed", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("due_diligence_expires_at", sa.DateTime()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id","vendor_code",name="uq_procurement_vendor_company_code"))

    op.create_table("procurement_requests", *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True)), sa.Column("vendor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reference", sa.String(100), nullable=False), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text()), sa.Column("category", sa.String(100)),
        sa.Column("amount", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("currency", sa.String(3), server_default="LSL", nullable=False),
        sa.Column("status", sa.String(40), server_default="draft", nullable=False), sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True)), sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("needed_by", sa.Date()), sa.Column("submitted_at", sa.DateTime()), sa.Column("approved_at", sa.DateTime()), sa.Column("rejected_at", sa.DateTime()), sa.Column("decision_note", sa.Text()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["branch_id"],["company_branches.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"],["procurement_vendors.id"],ondelete="SET NULL"), sa.ForeignKeyConstraint(["requested_by_user_id"],["users.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id","reference",name="uq_procurement_request_company_reference"))

    op.create_table("company_budget_plans", *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True)), sa.Column("fiscal_year", sa.String(20), nullable=False),
        sa.Column("version", sa.String(40), server_default="baseline", nullable=False), sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("currency", sa.String(3), server_default="LSL", nullable=False), sa.Column("notes", sa.Text()), sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True)), sa.Column("approved_at", sa.DateTime()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["branch_id"],["company_branches.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id","fiscal_year","version",name="uq_company_budget_plan_year_version"))

    op.create_table("company_budget_lines", *_audit_columns(),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True)),
        sa.Column("cost_centre", sa.String(100), nullable=False), sa.Column("account_code", sa.String(100), nullable=False), sa.Column("period", sa.String(20), nullable=False),
        sa.Column("budget_amount", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("forecast_amount", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("actual_amount", sa.Numeric(18,2), server_default="0", nullable=False), sa.Column("note", sa.Text()),
        sa.ForeignKeyConstraint(["plan_id"],["company_budget_plans.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"],["company_branches.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id","cost_centre","account_code","period",name="uq_company_budget_line_dimension"))

    op.create_table("internal_audit_engagements", *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True)), sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("title", sa.String(240), nullable=False), sa.Column("audit_area", sa.String(120), nullable=False), sa.Column("risk_rating", sa.String(30)), sa.Column("status", sa.String(40), server_default="planned", nullable=False),
        sa.Column("lead_auditor_user_id", postgresql.UUID(as_uuid=True)), sa.Column("planned_start", sa.Date()), sa.Column("planned_end", sa.Date()), sa.Column("started_at", sa.DateTime()), sa.Column("closed_at", sa.DateTime()),
        sa.Column("scope", sa.Text()), sa.Column("conclusion", sa.Text()), sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["branch_id"],["company_branches.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_auditor_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("company_id","reference",name="uq_internal_audit_engagement_company_reference"))

    op.create_table("internal_audit_findings", *_audit_columns(),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True)),
        sa.Column("finding_number", sa.String(40), nullable=False), sa.Column("title", sa.String(240), nullable=False), sa.Column("severity", sa.String(30), server_default="medium", nullable=False), sa.Column("status", sa.String(30), server_default="open", nullable=False),
        sa.Column("observation", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text()), sa.Column("management_response", sa.Text()), sa.Column("owner_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("due_at", sa.DateTime()), sa.Column("remediated_at", sa.DateTime()), sa.Column("closure_evidence", sa.Text()), sa.Column("verified_at", sa.DateTime()), sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(["engagement_id"],["internal_audit_engagements.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["company_id"],["loan_companies.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["branch_id"],["company_branches.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"],["users.id"],ondelete="SET NULL"), sa.ForeignKeyConstraint(["verified_by_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engagement_id","finding_number",name="uq_internal_audit_finding_number"))

    for table, cols in {
        "procurement_vendors": ("company_id","vendor_code","status","risk_rating"),
        "procurement_requests": ("company_id","branch_id","vendor_id","reference","status","needed_by"),
        "company_budget_plans": ("company_id","branch_id","fiscal_year","status"),
        "company_budget_lines": ("plan_id","company_id","branch_id","cost_centre","account_code","period"),
        "internal_audit_engagements": ("company_id","branch_id","reference","audit_area","risk_rating","status"),
        "internal_audit_findings": ("engagement_id","company_id","branch_id","finding_number","severity","status","due_at"),
    }.items():
        for col in cols:
            op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    for table in ("internal_audit_findings","internal_audit_engagements","company_budget_lines","company_budget_plans","procurement_requests","procurement_vendors"):
        op.drop_table(table)
