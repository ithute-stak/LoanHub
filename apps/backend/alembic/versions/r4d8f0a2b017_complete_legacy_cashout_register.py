"""Complete the searchable legacy cash-out register.

Revision ID: r4d8f0a2b017
Revises: q1c4e7g0h016
Create Date: 2026-08-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "r4d8f0a2b017"
down_revision = "q1c4e7g0h016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("legacy_loan_captures", sa.Column("cashout_book_number", sa.String(length=80), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("page_number", sa.String(length=80), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("entry_number", sa.String(length=80), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("next_of_kin_work_phone", sa.String(length=30), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("total_repayable", sa.Numeric(15, 2), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("amount_paid", sa.Numeric(15, 2), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("installment_count", sa.Integer(), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("installment_amount", sa.Numeric(15, 2), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("repayment_type", sa.String(length=20), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("calculation_method", sa.String(length=80), nullable=True))
    op.add_column(
        "legacy_loan_captures",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "legacy_loan_captures",
        sa.Column("posted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("legacy_loan_captures", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("legacy_loan_captures", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_legacy_loan_captures_reviewed_by_user",
        "legacy_loan_captures",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_legacy_loan_captures_posted_by_user",
        "legacy_loan_captures",
        "users",
        ["posted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_legacy_loan_captures_posted_by_user", "legacy_loan_captures", type_="foreignkey")
    op.drop_constraint("fk_legacy_loan_captures_reviewed_by_user", "legacy_loan_captures", type_="foreignkey")
    for column in (
        "reviewed_at",
        "review_notes",
        "posted_by_user_id",
        "reviewed_by_user_id",
        "calculation_method",
        "repayment_type",
        "installment_amount",
        "installment_count",
        "amount_paid",
        "total_repayable",
        "next_of_kin_work_phone",
        "entry_number",
        "page_number",
        "cashout_book_number",
    ):
        op.drop_column("legacy_loan_captures", column)
