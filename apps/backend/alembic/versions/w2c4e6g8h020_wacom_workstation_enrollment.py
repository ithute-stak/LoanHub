"""Wacom workstation enrollment and replay-safe PoP challenges.

Revision ID: w2c4e6g8h020
Revises: x1w2s3g4n517
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "w2c4e6g8h020"
down_revision = "x1w2s3g4n517"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
    ]


def upgrade():
    op.create_table(
        "wacom_workstation_enrollments",
        *audit_columns(),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operator_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ed25519_public_key", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "workstation_id", name="uq_wacom_enrollment_company_workstation"),
        sa.CheckConstraint("status IN ('pending','active','revoked')", name="ck_wacom_enrollment_status"),
        sa.CheckConstraint("octet_length(ed25519_public_key) = 32", name="ck_wacom_enrollment_public_key_bytes"),
    )
    op.create_index("ix_wacom_enrollment_tenant_status", "wacom_workstation_enrollments", ["company_id", "status"])
    op.create_table(
        "wacom_workstation_challenges",
        *audit_columns(),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("enrollment_id", UUID(as_uuid=True), sa.ForeignKey("wacom_workstation_enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("nonce", name="uq_wacom_challenge_nonce"),
        sa.CheckConstraint("octet_length(nonce) = 32", name="ck_wacom_challenge_nonce_bytes"),
    )
    op.create_index("ix_wacom_challenge_session", "wacom_workstation_challenges", ["company_id", "session_id"])


def downgrade():
    op.drop_index("ix_wacom_challenge_session", table_name="wacom_workstation_challenges")
    op.drop_table("wacom_workstation_challenges")
    op.drop_index("ix_wacom_enrollment_tenant_status", table_name="wacom_workstation_enrollments")
    op.drop_table("wacom_workstation_enrollments")
