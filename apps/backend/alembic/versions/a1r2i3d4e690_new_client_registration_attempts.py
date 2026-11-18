"""Durable new-only client registration idempotency attempts.

Revision ID: a1r2i3d4e690
Revises: z9n3p5q7r800
Create Date: 2026-11-18

No production application code activates registration in this revision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1r2i3d4e690"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "new_client_registration_attempts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="reserved"),
        sa.Column("client_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_account_id"],
                                ["company_borrower_accounts.id"],
                                ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key",
            name="uq_new_client_registration_company_idempotency"),
        sa.CheckConstraint(
            "status IN ('reserved','completed','rejected')",
            name="ck_new_client_registration_status"),
    )
    op.create_index("ix_new_client_reg_attempt_company",
                    "new_client_registration_attempts", ["company_id"])
    op.create_index("ix_new_client_reg_attempt_branch",
                    "new_client_registration_attempts", ["branch_id"])
    op.create_index("ix_new_client_reg_attempt_employee",
                    "new_client_registration_attempts", ["employee_user_id"])


def downgrade() -> None:
    op.drop_index("ix_new_client_reg_attempt_employee",
                  table_name="new_client_registration_attempts")
    op.drop_index("ix_new_client_reg_attempt_branch",
                  table_name="new_client_registration_attempts")
    op.drop_index("ix_new_client_reg_attempt_company",
                  table_name="new_client_registration_attempts")
    op.drop_table("new_client_registration_attempts")
