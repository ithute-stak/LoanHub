"""Add explicitly non-operative workstation-key proof to Wacom ceremony record.

Revision ID: f1a2b3c4d623
Revises: e0f1a2b3c512
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f1a2b3c4d623"
down_revision = "e0f1a2b3c512"
branch_labels = None
depends_on = None


def upgrade():
    table = "wacom_execution_ceremony_challenges"
    op.add_column(table, sa.Column("workstation_proof_at", sa.DateTime(timezone=True)))
    op.add_column(table, sa.Column(
        "workstation_proof_by", UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
    ))
    op.add_column(table, sa.Column("workstation_proof_sha256", sa.String(64)))
    op.create_check_constraint(
        "ck_wacom_ceremony_workstation_proof_complete",
        table,
        "(workstation_proof_at IS NULL AND workstation_proof_by IS NULL AND "
        "workstation_proof_sha256 IS NULL) OR "
        "(workstation_proof_at IS NOT NULL AND workstation_proof_by IS NOT NULL "
        "AND length(workstation_proof_sha256) = 64)",
    )


def downgrade():
    table = "wacom_execution_ceremony_challenges"
    op.drop_constraint("ck_wacom_ceremony_workstation_proof_complete", table, type_="check")
    op.drop_column(table, "workstation_proof_sha256")
    op.drop_column(table, "workstation_proof_by")
    op.drop_column(table, "workstation_proof_at")
