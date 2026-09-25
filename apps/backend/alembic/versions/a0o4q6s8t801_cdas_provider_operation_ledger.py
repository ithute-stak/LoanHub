"""CDAS provider operation ledger

Revision ID: a0o4q6s8t801
Revises: z9n3p5q7r800
Create Date: 2026-09-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a0o4q6s8t801"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cdas_provider_operations",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("operation_type", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=40), server_default="prepared", nullable=False),
        sa.Column("employee_no", sa.String(length=100), nullable=True),
        sa.Column("deduction_id", sa.Integer(), nullable=True),
        sa.Column("reference_no", sa.String(length=200), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("response_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("requires_reconciliation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_cdas_provider_operations_company_id", "cdas_provider_operations", ["company_id"])
    op.create_index("ix_cdas_provider_operations_branch_id", "cdas_provider_operations", ["branch_id"])
    op.create_index("ix_cdas_provider_operations_actor_user_id", "cdas_provider_operations", ["actor_user_id"])
    op.create_index("ix_cdas_provider_operations_environment", "cdas_provider_operations", ["environment"])
    op.create_index("ix_cdas_provider_operations_operation_type", "cdas_provider_operations", ["operation_type"])
    op.create_index("ix_cdas_provider_operations_state", "cdas_provider_operations", ["state"])
    op.create_index("ix_cdas_provider_operations_employee_no", "cdas_provider_operations", ["employee_no"])
    op.create_index("ix_cdas_provider_operations_deduction_id", "cdas_provider_operations", ["deduction_id"])
    op.create_index("ix_cdas_provider_operations_reference_no", "cdas_provider_operations", ["reference_no"])
    op.create_index("ix_cdas_provider_operations_fingerprint", "cdas_provider_operations", ["fingerprint"])
    op.create_index("ix_cdas_provider_operations_requires_reconciliation", "cdas_provider_operations", ["requires_reconciliation"])
    op.create_index("ix_cdas_provider_operations_company_created", "cdas_provider_operations", ["company_id", "created_at"])
    op.create_index(
        "uq_cdas_provider_operation_unresolved_fingerprint",
        "cdas_provider_operations",
        ["company_id", "environment", "fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('prepared','submitting','acknowledged','unknown_provider_state','requires_reconciliation')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_cdas_provider_operation_unresolved_fingerprint", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_company_created", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_requires_reconciliation", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_fingerprint", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_reference_no", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_deduction_id", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_employee_no", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_state", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_operation_type", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_environment", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_actor_user_id", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_branch_id", table_name="cdas_provider_operations")
    op.drop_index("ix_cdas_provider_operations_company_id", table_name="cdas_provider_operations")
    op.drop_table("cdas_provider_operations")
