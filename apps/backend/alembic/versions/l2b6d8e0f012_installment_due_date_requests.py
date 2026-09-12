"""Add borrower installment due-date adjustment requests.

Revision ID: l2b6d8e0f012
Revises: k1a5c7d9e011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "l2b6d8e0f012"
down_revision = "k1a5c7d9e011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installment_due_date_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_due_date", sa.Date(), nullable=False),
        sa.Column("requested_due_date", sa.Date(), nullable=False),
        sa.Column("borrower_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("company_response", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installment_id"], ["repayment_installments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_installment_due_date_request_status",
        ),
    )
    for column in ("loan_id", "installment_id", "borrower_id", "company_id", "branch_id", "status", "decided_by_user_id"):
        op.create_index(
            f"ix_installment_due_date_requests_{column}",
            "installment_due_date_requests",
            [column],
        )
    op.create_index(
        "ix_installment_due_date_requests_company_status_created",
        "installment_due_date_requests",
        ["company_id", "status", "created_at"],
    )
    op.create_index(
        "uq_installment_due_date_requests_pending_installment",
        "installment_due_date_requests",
        ["installment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_installment_due_date_requests_pending_installment",
        table_name="installment_due_date_requests",
    )
    op.drop_index("ix_installment_due_date_requests_company_status_created", table_name="installment_due_date_requests")
    for column in ("decided_by_user_id", "status", "branch_id", "company_id", "borrower_id", "installment_id", "loan_id"):
        op.drop_index(f"ix_installment_due_date_requests_{column}", table_name="installment_due_date_requests")
    op.drop_table("installment_due_date_requests")
