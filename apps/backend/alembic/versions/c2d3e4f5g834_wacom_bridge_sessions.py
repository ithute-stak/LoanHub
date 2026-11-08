"""Wacom device-proof-bound sessions.

Revision ID: c2d3e4f5g834
Revises: b1c2d3e4f823
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c2d3e4f5g834"
down_revision = "b1c2d3e4f823"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_bridge_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_sha256", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_wacom_bridge_session_actor", "wacom_bridge_sessions",
                    ["company_id", "employee_user_id", "workstation_id"])


def downgrade():
    op.drop_index("ix_wacom_bridge_session_actor", table_name="wacom_bridge_sessions")
    op.drop_table("wacom_bridge_sessions")
