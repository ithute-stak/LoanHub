"""Add quarantined signature bridge import table.

Revision ID: sb20261105q01
Revises: w2c4e6g8h020
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "sb20261105q01"
down_revision = "w2c4e6g8h020"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "signature_bridge_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signer_kind", sa.String(length=12), nullable=False),
        sa.Column("signer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payload_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("consent_reference", sa.String(length=180), nullable=False),
        sa.Column("phone_aliases_digest", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_identity_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "source_record_id", name="uq_signature_bridge_company_source"),
    )
    op.create_index("ix_signature_bridge_company_signer", "signature_bridge_imports", ["company_id", "signer_id"])

def downgrade():
    op.drop_index("ix_signature_bridge_company_signer", table_name="signature_bridge_imports")
    op.drop_table("signature_bridge_imports")
