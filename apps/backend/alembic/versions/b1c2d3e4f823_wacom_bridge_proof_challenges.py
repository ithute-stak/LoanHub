"""First-party device proof challenges for multi-operator Wacom PC bridges.

Revision ID: b1c2d3e4f823
Revises: a1b2c3d4e812
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b1c2d3e4f823"
down_revision = "a1b2c3d4e812"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_bridge_challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("nonce", sa.LargeBinary(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("nonce", name="uq_wacom_bridge_challenge_nonce"),
    )
    op.create_index("ix_wacom_bridge_challenge_operator", "wacom_bridge_challenges",
                    ["company_id", "employee_user_id", "workstation_id"])


def downgrade():
    op.drop_index("ix_wacom_bridge_challenge_operator", table_name="wacom_bridge_challenges")
    op.drop_table("wacom_bridge_challenges")
