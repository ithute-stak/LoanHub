"""Create isolated Wacom two-person finalization approvals.

Revision ID: e4f5a6b7c956
Revises: d3e4f5a6b845
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e4f5a6b7c956"
down_revision = "d3e4f5a6b845"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_finalization_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reference", sa.String(180)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired','consumed')", name="ck_wacom_final_approval_state"),
        sa.UniqueConstraint("intent_id", name="uq_wacom_finalization_intent"),
    )
    op.create_index("ix_wacom_finalization_company_status", "wacom_finalization_approvals", ["company_id", "status"])


def downgrade():
    op.drop_index("ix_wacom_finalization_company_status", table_name="wacom_finalization_approvals")
    op.drop_table("wacom_finalization_approvals")
