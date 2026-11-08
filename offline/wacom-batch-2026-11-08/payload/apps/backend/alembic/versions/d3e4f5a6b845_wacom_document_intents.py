"""Wacom document intents — additive, deliberately separate from signed contracts.

Revision ID: d3e4f5a6b845
Revises: c2d3e4f5g834
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "d3e4f5a6b845"
down_revision = "c2d3e4f5g834"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_document_intents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("borrower_id", UUID(as_uuid=True), sa.ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_file_id", UUID(as_uuid=True), sa.ForeignKey("managed_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operator_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("document_version", sa.String(80), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="prepared"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_reference", sa.String(180)),
        sa.Column("consent_commitment_sha256", sa.String(64)),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_file_id", UUID(as_uuid=True), sa.ForeignKey("managed_files.id", ondelete="RESTRICT")),
        sa.Column("evidence_sha256", sa.String(64)),
        sa.Column("review_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("review_at", sa.DateTime(timezone=True)),
        sa.Column("review_reference", sa.String(180)),
        sa.Column("review_reason", sa.Text()),
        sa.CheckConstraint("status IN ('prepared','consented','evidence_uploaded','verified','rejected','expired','cancelled')", name="ck_wacom_doc_intent_status"),
        sa.CheckConstraint("length(document_sha256) = 64 AND length(binding_sha256) = 64", name="ck_wacom_doc_hashes"),
        sa.UniqueConstraint("company_id", "contract_id", "document_sha256", "borrower_id", name="uq_wacom_doc_intent_exact_document"),
    )
    op.create_index("ix_wacom_doc_intent_actor", "wacom_document_intents", ["company_id", "operator_user_id", "status"])


def downgrade():
    op.drop_index("ix_wacom_doc_intent_actor", table_name="wacom_document_intents")
    op.drop_table("wacom_document_intents")
