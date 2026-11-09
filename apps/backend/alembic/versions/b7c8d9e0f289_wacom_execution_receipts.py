"""Wacom one-record-per-contract execution receipt schema, signing still off.

Revision ID: b7c8d9e0f289
Revises: a6b7c8d9e178
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b7c8d9e0f289"
down_revision = "a6b7c8d9e178"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_execution_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authorization_id", UUID(as_uuid=True), sa.ForeignKey("wacom_execution_authorizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("packet_id", UUID(as_uuid=True), sa.ForeignKey("wacom_finalization_packets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="reserved"),
        sa.Column("reserved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_file_id", UUID(as_uuid=True), sa.ForeignKey("managed_files.id", ondelete="RESTRICT")),
        sa.Column("executed_pdf_sha256", sa.String(64)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "contract_id", name="uq_wacom_exec_receipt_company_contract"),
        sa.UniqueConstraint("authorization_id", name="uq_wacom_exec_receipt_authorization"),
        sa.UniqueConstraint("intent_id", name="uq_wacom_exec_receipt_intent"),
        sa.CheckConstraint(
            "status IN ('reserved','executed','aborted')",
            name="ck_wacom_execution_receipt_status",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64 AND length(evidence_sha256) = 64 "
            "AND length(binding_sha256) = 64",
            name="ck_wacom_execution_receipt_hash_length",
        ),
        sa.CheckConstraint(
            "(status <> 'executed') OR "
            "(executed_file_id IS NOT NULL AND executed_pdf_sha256 IS NOT NULL "
            "AND executed_at IS NOT NULL AND length(executed_pdf_sha256) = 64)",
            name="ck_wacom_execution_receipt_completed",
        ),
    )
    op.create_index(
        "ix_wacom_execution_receipt_company", "wacom_execution_receipts",
        ["company_id", "status"],
    )


def downgrade():
    op.drop_index("ix_wacom_execution_receipt_company", table_name="wacom_execution_receipts")
    op.drop_table("wacom_execution_receipts")
