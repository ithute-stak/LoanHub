"""Wacom multi-operator assignment foundation, additive only.

Revision ID: a1b2c3d4e812
Revises: z9n3p5q7r800
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "a1b2c3d4e812"
down_revision = "z9n3p5q7r800"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wacom_workstation_operators",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workstation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("company_branches.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "workstation_id", "employee_user_id", name="uq_wacom_pc_company_device_employee"),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_wacom_pc_operator_status"),
    )
    op.create_index("ix_wacom_pc_operator_employee", "wacom_workstation_operators", ["company_id", "employee_user_id", "status"])


def downgrade():
    op.drop_index("ix_wacom_pc_operator_employee", table_name="wacom_workstation_operators")
    op.drop_table("wacom_workstation_operators")
