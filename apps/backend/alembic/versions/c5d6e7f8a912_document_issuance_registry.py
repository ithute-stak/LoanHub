"""Create tenant document issuance registry and append-event ledger.

Revision ID: c5d6e7f8a912
Revises: b4c5d6e7f801

Draft feature schema only. Do not activate the issuance API until tenant RLS,
runtime grants, immutable storage and security acceptance tests are certified.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c5d6e7f8a912"
down_revision = "b4c5d6e7f801"
branch_labels = None
depends_on = None


def _audit_columns():
    return (
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
    )


def upgrade():
    op.create_table(
        "document_issuances",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("public_id", sa.String(96), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(120), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stamp_configuration_version", sa.Integer(), nullable=False),
        sa.Column("source_pdf_sha256", sa.String(64), nullable=False),
        sa.Column("final_pdf_sha256", sa.String(64), nullable=False),
        sa.Column("artifact_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("document_issuances.id", ondelete="RESTRICT")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("revocation_reason", sa.Text()),
        sa.UniqueConstraint("public_id", name="uq_document_issuances_public_id"),
        sa.UniqueConstraint("company_id", "idempotency_key",
                            name="uq_document_issuances_tenant_idempotency"),
        sa.UniqueConstraint("company_id", "source_type", "source_id",
                            "document_type", "version",
                            name="uq_document_issuances_source_version"),
        sa.CheckConstraint("version >= 1", name="ck_document_issuances_version_positive"),
        sa.CheckConstraint("status IN ('issued', 'revoked', 'superseded')",
                           name="ck_document_issuances_known_status"),
    )
    op.create_index("ix_document_issuances_company_id",
                    "document_issuances", ["company_id"])
    op.create_index("ix_document_issuances_tenant_source",
                    "document_issuances", ["company_id", "source_type", "source_id"])

    op.create_table(
        "document_issuance_events",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuance_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("document_issuances.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("detail", sa.Text()),
    )
    op.create_index("ix_document_issuance_events_company_id",
                    "document_issuance_events", ["company_id"])
    op.create_index("ix_document_issuance_events_issuance_time",
                    "document_issuance_events", ["issuance_id", "created_at"])


    # Restrict tenant reads and issuance registration from the beginning,
    # rather than relying on endpoint filters alone. PostgreSQL table owners
    # bypass normal RLS, so the deployed runtime must use a non-owner role
    # without BYPASSRLS; do not enable the new feature until role certification.
    tenant_predicate = (
        "current_setting('loanhub.actor_scope', true) = 'tenant' "
        "AND company_id = NULLIF(current_setting('loanhub.company_id', true), '')::uuid"
    )
    issuer_predicate = (
        tenant_predicate
        + " AND current_setting('loanhub.role', true) "
          "IN ('company_owner', 'company_admin')"
    )
    for table in ("document_issuances", "document_issuance_events"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(
            f"CREATE POLICY {table}_tenant_select ON {table} "
            f"FOR SELECT USING ({tenant_predicate})"
        ))
        actor_column = (
            "issued_by_user_id" if table == "document_issuances"
            else "actor_user_id"
        )
        op.execute(sa.text(
            f"CREATE POLICY {table}_tenant_insert ON {table} "
            f"FOR INSERT WITH CHECK ({issuer_predicate} "
            f"AND {actor_column} = NULLIF("
            f"current_setting('loanhub.user_id', true), '')::uuid)"
        ))
    # No tenant UPDATE/DELETE policy exists. The runtime role must have
    # SELECT/INSERT only; audited transitions need a separately reviewed
    # privileged operation.




def downgrade():
    # Restricted to pre-production/disposable databases. A production issuance
    # ledger must never be destroyed merely to roll back an application deploy.
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM document_issuances LIMIT 1) "
        "OR EXISTS (SELECT 1 FROM document_issuance_events LIMIT 1)"
    )).scalar():
        raise RuntimeError("Refusing downgrade with persisted document issuance history")
    for table in ("document_issuance_events", "document_issuances"):
        op.execute(sa.text(f"DROP POLICY {table}_tenant_insert ON {table}"))
        op.execute(sa.text(f"DROP POLICY {table}_tenant_select ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_document_issuance_events_issuance_time",
                  table_name="document_issuance_events")
    op.drop_index("ix_document_issuance_events_company_id",
                  table_name="document_issuance_events")
    op.drop_table("document_issuance_events")
    op.drop_index("ix_document_issuances_tenant_source",
                  table_name="document_issuances")
    op.drop_index("ix_document_issuances_company_id",
                  table_name="document_issuances")
    op.drop_table("document_issuances")
