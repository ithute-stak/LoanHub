"""Audit log for privileged, explicitly approved Data Center pilot transitions.

Revision ID: dc20261122002
Revises: dc20261122001

No company is enabled or disabled by this migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dc20261122002"
down_revision = "dc20261122001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loanhub_dc_pilot_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("operator", sa.String(120), nullable=False),
        sa.Column("approval_ref", sa.String(160), nullable=False),
        sa.Column("old_generation", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("new_generation", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("action IN ('activate', 'disable')",
                           name="ck_loanhub_dc_pilot_audit_action"),
    )
    op.execute("ALTER TABLE public.loanhub_dc_pilot_audit ENABLE ROW LEVEL SECURITY")
    # Audit is deliberately invisible to normal runtime connections.
    # Only privileged operators can insert and inspect this table.
    op.execute("REVOKE ALL ON public.loanhub_dc_pilot_audit FROM PUBLIC")
    op.execute("""
        DO $body$
        BEGIN
            IF to_regrole('loanhub_app') IS NOT NULL THEN
                REVOKE ALL ON TABLE public.loanhub_dc_pilot_audit FROM loanhub_app;
            END IF;
        END
        $body$
    """)


def downgrade():
    op.drop_table("loanhub_dc_pilot_audit")
