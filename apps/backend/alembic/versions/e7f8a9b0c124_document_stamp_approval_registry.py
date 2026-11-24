"""Draft tenant-isolated, append-only approved-stamp evidence registry.

Revision ID: e7f8a9b0c124
Revises: d6e7f8a9b013

This migration creates NO approval records and grants NO runtime privileges.
A separately reviewed privileged approval operation must append evidence only
after independently authorizing the approver and protecting the snapshot.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7f8a9b0c124"
down_revision = "d6e7f8a9b013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_stamp_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256_hex", sa.String(64), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "configuration_version",
                            name="uq_document_stamp_approvals_company_version"),
        sa.CheckConstraint("configuration_version >= 1",
                           name="ck_document_stamp_approvals_version_positive"),
        sa.CheckConstraint("status = 'approved'",
                           name="ck_document_stamp_approvals_approved_only"),
        sa.CheckConstraint("length(snapshot_sha256_hex) = 64",
                           name="ck_document_stamp_approvals_digest_length"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > approved_at",
                           name="ck_document_stamp_approvals_expiry_order"),
    )
    op.create_index("ix_document_stamp_approvals_company_id",
                    "document_stamp_approvals", ["company_id"])
    op.execute(sa.text(
        "ALTER TABLE document_stamp_approvals ENABLE ROW LEVEL SECURITY"
    ))
    op.execute(sa.text(
        "CREATE POLICY document_stamp_approvals_tenant_select "
        "ON document_stamp_approvals FOR SELECT USING ("
        "current_setting('loanhub.actor_scope', true) = 'tenant' "
        "AND company_id = NULLIF(current_setting('loanhub.company_id', true), '')::uuid"
        ")"
    ))
    # No tenant INSERT/UPDATE/DELETE policy. The application runtime MUST use a
    # non-owner, non-superuser, NOBYPASSRLS role granted SELECT only. The
    # registry must never be writable via normal request sessions.


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM document_stamp_approvals LIMIT 1)"
    )).scalar():
        raise RuntimeError(
            "Refusing downgrade with recorded official stamp approvals"
        )
    op.execute(sa.text(
        "DROP POLICY document_stamp_approvals_tenant_select "
        "ON document_stamp_approvals"
    ))
    op.drop_index("ix_document_stamp_approvals_company_id",
                  table_name="document_stamp_approvals")
    op.drop_table("document_stamp_approvals")
