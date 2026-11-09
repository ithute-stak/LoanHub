"""Archived Wacom reviewed PDF packets, never signed contracts.

Revision ID: f5a6b7c8d067
Revises: e4f5a6b7c956
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f5a6b7c8d067"
down_revision = "e4f5a6b7c956"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_finalization_packets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approval_id", UUID(as_uuid=True), sa.ForeignKey("wacom_finalization_approvals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("packet_file_id", UUID(as_uuid=True), sa.ForeignKey("managed_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("handwriting_sha256", sa.String(64), nullable=False),
        sa.Column("packet_sha256", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("approval_id", name="uq_wacom_packet_approval"),
        sa.UniqueConstraint("intent_id", name="uq_wacom_packet_intent"),
        sa.UniqueConstraint("contract_id", name="uq_wacom_packet_contract"),
    )
    op.create_index("ix_wacom_packet_company", "wacom_finalization_packets", ["company_id", "created_at"])


def downgrade():
    op.drop_index("ix_wacom_packet_company", table_name="wacom_finalization_packets")
    op.drop_table("wacom_finalization_packets")
