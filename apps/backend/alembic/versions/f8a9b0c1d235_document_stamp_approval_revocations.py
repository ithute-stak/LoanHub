"""Draft append-only revocation history for official company stamp approvals.

Revision ID: f8a9b0c1d235
Revises: e7f8a9b0c124

Only a separately reviewed privileged service may append a revocation.
Regular tenant runtime sessions receive no insert/update/delete permissions.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f8a9b0c1d235"
down_revision = "e7f8a9b0c124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_stamp_approval_revocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("document_stamp_approvals.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("approval_id",
                            name="uq_stamp_approval_revocations_approval_id"),
        sa.CheckConstraint("length(trim(reason)) >= 10",
                           name="ck_stamp_approval_revocations_reason"),
    )
    op.create_index("ix_stamp_approval_revocations_company",
                    "document_stamp_approval_revocations", ["company_id"])
    op.execute(sa.text(
        "ALTER TABLE document_stamp_approval_revocations ENABLE ROW LEVEL SECURITY"
    ))
    op.execute(sa.text(
        "CREATE POLICY document_stamp_approval_revocations_tenant_select "
        "ON document_stamp_approval_revocations FOR SELECT USING ("
        "current_setting('loanhub.actor_scope', true) = 'tenant' "
        "AND company_id = NULLIF(current_setting('loanhub.company_id', true), '')::uuid "
        "AND EXISTS ("
        "SELECT 1 FROM document_stamp_approvals a "
        "WHERE a.id = approval_id AND a.company_id = company_id"
        ")"
        ")"
    ))
    # No runtime INSERT/UPDATE/DELETE policy or privilege grant.


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM document_stamp_approval_revocations LIMIT 1)"
    )).scalar():
        raise RuntimeError("Refusing to erase historic stamp revocations")
    op.execute(sa.text(
        "DROP POLICY document_stamp_approval_revocations_tenant_select "
        "ON document_stamp_approval_revocations"
    ))
    op.drop_index("ix_stamp_approval_revocations_company",
                  table_name="document_stamp_approval_revocations")
    op.drop_table("document_stamp_approval_revocations")
