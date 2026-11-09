"""Separate, unconsumed Wacom signing permits (still no live signing).

Revision ID: a6b7c8d9e178
Revises: f5a6b7c8d067
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "a6b7c8d9e178"
down_revision = "f5a6b7c8d067"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_execution_authorizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("packet_id", UUID(as_uuid=True), sa.ForeignKey("wacom_finalization_packets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorized_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("authorized_at", sa.DateTime(timezone=True)),
        sa.Column("authorization_reference", sa.String(180)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("intent_id", name="uq_wacom_execution_auth_intent"),
        sa.UniqueConstraint("contract_id", name="uq_wacom_execution_auth_contract"),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','expired','consumed','cancelled')",
            name="ck_wacom_execution_authorization_status",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64 AND length(evidence_sha256) = 64 AND length(binding_sha256) = 64",
            name="ck_wacom_execution_auth_hash_lengths",
        ),
    )
    op.create_index("ix_wacom_execution_auth_company_status", "wacom_execution_authorizations", ["company_id", "status"])


def downgrade():
    op.drop_index("ix_wacom_execution_auth_company_status", table_name="wacom_execution_authorizations")
    op.drop_table("wacom_execution_authorizations")
