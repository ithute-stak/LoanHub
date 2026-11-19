"""Add opt-in Principal x payment policy and immutable per-loan assignment.

Revision ID: p1x2m3o4d590
Revises: a1r2i3d4e690

Schema-only: existing loans remain unassigned and use the existing model.
No company is opted in, and live collections remain disabled.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p1x2m3o4d590"
down_revision: Union[str, Sequence[str], None] = "a1r2i3d4e690"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    # Required for the composite FK: loan and company must match in one row.
    op.create_unique_constraint(
        "uq_client_loan_id_company", "client_company_loan", ["id", "company_id"]
    )
    op.create_table(
        "company_payment_model_settings",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_model", sa.String(length=30), server_default="existing", nullable=False),
        sa.Column("allow_new_loans", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enable_live_collections", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", name="uq_company_payment_model_settings_company"),
        sa.CheckConstraint("default_model IN ('existing', 'principal_x')", name="ck_company_payment_model_allowed"),
        sa.CheckConstraint("NOT enable_live_collections OR allow_new_loans", name="ck_company_payment_model_live_requires_opt_in"),
        sa.CheckConstraint("NOT enable_live_collections OR default_model = 'principal_x'", name="ck_company_payment_model_live_requires_default"),
    )
    op.create_index("ix_company_payment_model_settings_company_id", "company_payment_model_settings", ["company_id"])
    op.create_table(
        "loan_payment_model_assignments",
        *_audit_columns(),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_model", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["loan_id", "company_id"], ["client_company_loan.id", "client_company_loan.company_id"],
            name="fk_loan_payment_model_assignment_owner", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("loan_id", name="uq_loan_payment_model_assignment_loan"),
        sa.CheckConstraint("payment_model IN ('existing', 'principal_x')", name="ck_loan_payment_model_allowed"),
    )
    op.create_index("ix_loan_payment_model_assignments_loan_id", "loan_payment_model_assignments", ["loan_id"])
    op.create_index("ix_loan_payment_model_assignments_company_id", "loan_payment_model_assignments", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_loan_payment_model_assignments_company_id", table_name="loan_payment_model_assignments")
    op.drop_index("ix_loan_payment_model_assignments_loan_id", table_name="loan_payment_model_assignments")
    op.drop_table("loan_payment_model_assignments")
    op.drop_index("ix_company_payment_model_settings_company_id", table_name="company_payment_model_settings")
    op.drop_table("company_payment_model_settings")
    op.drop_constraint("uq_client_loan_id_company", "client_company_loan", type_="unique")
