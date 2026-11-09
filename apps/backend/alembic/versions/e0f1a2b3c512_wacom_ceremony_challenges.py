"""Non-operative one-time Wacom signing ceremony challenge.

Revision ID: e0f1a2b3c512
Revises: d9e0f1a2b401
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e0f1a2b3c512"
down_revision = "d9e0f1a2b401"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_execution_ceremony_challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("borrower_id", UUID(as_uuid=True), sa.ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authorization_id", UUID(as_uuid=True), sa.ForeignKey("wacom_execution_authorizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receipt_id", UUID(as_uuid=True), sa.ForeignKey("wacom_execution_receipts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_sha256", sa.String(64), nullable=False),
        sa.Column("candidate_sha256", sa.String(64), nullable=False),
        sa.Column("field_binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "contract_id", name="uq_wacom_ceremony_company_contract"),
        sa.UniqueConstraint("authorization_id", name="uq_wacom_ceremony_authorization"),
        sa.UniqueConstraint("receipt_id", name="uq_wacom_ceremony_receipt"),
        sa.UniqueConstraint("challenge_sha256", name="uq_wacom_ceremony_challenge_digest"),
        sa.CheckConstraint("status IN ('pending','expired','cancelled','verified','consumed')", name="ck_wacom_ceremony_status"),
        sa.CheckConstraint("length(challenge_sha256) = 64 AND length(candidate_sha256) = 64 AND length(field_binding_sha256) = 64", name="ck_wacom_ceremony_hash_lengths"),
        sa.CheckConstraint(
            "(status = 'pending' AND verified_at IS NULL AND consumed_at IS NULL) OR "
            "(status IN ('expired','cancelled') AND consumed_at IS NULL) OR "
            "(status = 'verified' AND verified_at IS NOT NULL AND consumed_at IS NULL) OR "
            "(status = 'consumed' AND verified_at IS NOT NULL AND consumed_at IS NOT NULL)",
            name="ck_wacom_ceremony_state_evidence",
        ),
    )
    op.create_index(
        "ix_wacom_ceremony_company_status",
        "wacom_execution_ceremony_challenges", ["company_id", "status"],
    )


def downgrade():
    op.drop_index("ix_wacom_ceremony_company_status", table_name="wacom_execution_ceremony_challenges")
    op.drop_table("wacom_execution_ceremony_challenges")
