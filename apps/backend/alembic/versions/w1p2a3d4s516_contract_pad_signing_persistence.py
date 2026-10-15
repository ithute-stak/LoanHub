"""Persist contract-bound pad signing sessions and encrypted evidence references.

Revision ID: w1p2a3d4s516
Revises: z9n3p5q7r800
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "w1p2a3d4s516"
down_revision = "z9n3p5q7r800"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_pad_signing_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operator_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("verified_identity_at", sa.DateTime(timezone=True)),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("consent_version", sa.String(80)),
        sa.Column("evidence_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["loan_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('created','consented','captured','completed','expired','cancelled')", name="ck_pad_session_status"),
        sa.CheckConstraint("length(contract_hash) = 64", name="ck_pad_contract_hash_length"),
    )
    op.create_index("ix_pad_sessions_company_contract", "contract_pad_signing_sessions", ["company_id", "contract_id"])
    op.create_table(
        "contract_pad_capture_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_storage_key", sa.Text(), nullable=False),
        sa.Column("capture_source", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["contract_pad_signing_sessions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("capture_source IN ('pointer','wacom_stu')", name="ck_pad_capture_source"),
    )
    op.create_index("ix_pad_capture_company", "contract_pad_capture_evidence", ["company_id"])


def downgrade():
    op.drop_index("ix_pad_capture_company", table_name="contract_pad_capture_evidence")
    op.drop_table("contract_pad_capture_evidence")
    op.drop_index("ix_pad_sessions_company_contract", table_name="contract_pad_signing_sessions")
    op.drop_table("contract_pad_signing_sessions")
