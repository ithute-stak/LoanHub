"""add specialised company operations phase one

Revision ID: p9v0x1z2a301
Revises: n8u9w0y1z201
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p9v0x1z2a301"
down_revision = "n8u9w0y1z201"
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
    op.create_table(
        "crm_relationship_cases",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("relationship_stage", sa.String(40), server_default="active", nullable=False),
        sa.Column("segment", sa.String(60), nullable=True),
        sa.Column("status", sa.String(30), server_default="open", nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("next_action_at", sa.DateTime(), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(), nullable=True),
        sa.Column("contact_preference", sa.String(40), nullable=True),
        sa.Column("retention_risk", sa.String(30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_crm_relationship_case_company_reference"),
    )
    for col in ("company_id", "branch_id", "borrower_id", "loan_id", "reference", "relationship_stage", "segment", "status", "assigned_user_id", "next_action_at", "retention_risk"):
        op.create_index(f"ix_crm_relationship_cases_{col}", "crm_relationship_cases", [col])

    op.create_table(
        "collateral_assets",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("asset_type", sa.String(60), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ownership_name", sa.String(240), nullable=False),
        sa.Column("ownership_reference", sa.String(180), nullable=True),
        sa.Column("valuation_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("valuation_date", sa.DateTime(), nullable=True),
        sa.Column("valuer_name", sa.String(240), nullable=True),
        sa.Column("currency", sa.String(3), server_default="LSL", nullable=False),
        sa.Column("status", sa.String(30), server_default="held", nullable=False),
        sa.Column("perfected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("perfection_reference", sa.String(180), nullable=True),
        sa.Column("insured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("insurance_expiry_at", sa.DateTime(), nullable=True),
        sa.Column("release_requested_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("released_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_collateral_asset_company_reference"),
    )
    for col in ("company_id", "branch_id", "borrower_id", "loan_id", "reference", "asset_type", "status", "perfected"):
        op.create_index(f"ix_collateral_assets_{col}", "collateral_assets", [col])

    op.create_table(
        "legal_recovery_matters",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), server_default="pre_legal", nullable=False),
        sa.Column("legal_stage", sa.String(50), server_default="pre_action", nullable=False),
        sa.Column("counsel_name", sa.String(240), nullable=True),
        sa.Column("court_name", sa.String(240), nullable=True),
        sa.Column("court_case_number", sa.String(160), nullable=True),
        sa.Column("claim_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("legal_costs", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="LSL", nullable=False),
        sa.Column("next_court_at", sa.DateTime(), nullable=True),
        sa.Column("limitation_deadline_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_case_id"], ["collection_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_legal_recovery_matter_company_reference"),
    )
    for col in ("company_id", "branch_id", "borrower_id", "loan_id", "collection_case_id", "reference", "status", "legal_stage", "court_case_number", "next_court_at", "limitation_deadline_at", "assigned_user_id"):
        op.create_index(f"ix_legal_recovery_matters_{col}", "legal_recovery_matters", [col])

    op.create_table(
        "customer_complaint_cases",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("channel", sa.String(40), server_default="internal", nullable=False),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(30), server_default="normal", nullable=False),
        sa.Column("status", sa.String(40), server_default="open", nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(), nullable=False),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("regulatory_reportable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_customer_complaint_case_company_reference"),
    )
    for col in ("company_id", "branch_id", "borrower_id", "loan_id", "reference", "category", "channel", "severity", "status", "assigned_user_id", "sla_due_at", "regulatory_reportable"):
        op.create_index(f"ix_customer_complaint_cases_{col}", "customer_complaint_cases", [col])

    op.create_table(
        "company_operation_events",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("company_id", "branch_id", "module", "record_id", "event_type"):
        op.create_index(f"ix_company_operation_events_{col}", "company_operation_events", [col])


def downgrade() -> None:
    op.drop_table("company_operation_events")
    op.drop_table("customer_complaint_cases")
    op.drop_table("legal_recovery_matters")
    op.drop_table("collateral_assets")
    op.drop_table("crm_relationship_cases")
