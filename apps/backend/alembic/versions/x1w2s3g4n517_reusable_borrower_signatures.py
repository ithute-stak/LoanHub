"""Borrower signature vault metadata and contract-specific consent grants.

Revision ID: x1w2s3g4n517
Revises: w1p2a3d4s516, p6a1r2p3o901
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "x1w2s3g4n517"
down_revision = ("w1p2a3d4s516", "p6a1r2p3o901")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "borrower_saved_signatures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("borrower_id", UUID(as_uuid=True), sa.ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_session_id", UUID(as_uuid=True), sa.ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("encrypted_storage_key", sa.Text(), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("capture_source", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("reuse_opt_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_saved_signature_status"),
        sa.CheckConstraint("length(evidence_sha256) = 64", name="ck_saved_signature_hash_length"),
    )
    op.create_index("ix_saved_signature_tenant_borrower", "borrower_saved_signatures", ["company_id", "borrower_id"])
    op.create_table(
        "borrower_signature_use_authorizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("borrower_id", UUID(as_uuid=True), sa.ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("signature_id", UUID(as_uuid=True), sa.ForeignKey("borrower_saved_signatures.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="authorized"),
        sa.Column("verified_identity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("explicit_consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.UniqueConstraint("company_id", "contract_id", name="uq_signature_use_company_contract"),
        sa.CheckConstraint("status IN ('authorized','used','cancelled')", name="ck_signature_use_status"),
        sa.CheckConstraint("length(contract_hash) = 64", name="ck_signature_use_contract_hash"),
    )
    op.create_index("ix_signature_use_tenant_borrower", "borrower_signature_use_authorizations", ["company_id", "borrower_id"])


def downgrade():
    op.drop_index("ix_signature_use_tenant_borrower", table_name="borrower_signature_use_authorizations")
    op.drop_table("borrower_signature_use_authorizations")
    op.drop_index("ix_saved_signature_tenant_borrower", table_name="borrower_saved_signatures")
    op.drop_table("borrower_saved_signatures")
