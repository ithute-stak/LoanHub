"""external debt installment tracking

Revision ID: a0p4r6s8t910
Revises: z9n3p5q7r800
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a0p4r6s8t910"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("borrower_debt_obligations", sa.Column("started_on", sa.Date(), nullable=True))
    op.add_column(
        "borrower_debt_obligations",
        sa.Column("installment_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "borrower_debt_obligations",
        sa.Column("installment_frequency", sa.String(length=30), server_default="monthly", nullable=False),
    )
    op.add_column("borrower_debt_obligations", sa.Column("total_installments", sa.Integer(), nullable=True))
    op.add_column(
        "borrower_debt_obligations",
        sa.Column("installments_paid", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("borrower_debt_obligations", sa.Column("remaining_installments", sa.Integer(), nullable=True))
    op.add_column("borrower_debt_obligations", sa.Column("next_due_date", sa.Date(), nullable=True))
    op.add_column(
        "borrower_debt_obligations",
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
    )
    op.add_column("borrower_debt_obligations", sa.Column("last_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "borrower_debt_obligations",
        sa.Column("last_reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("borrower_debt_obligations", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_bdo_status", "borrower_debt_obligations", ["status"], unique=False)
    op.create_index("ix_bdo_reviewer", "borrower_debt_obligations", ["last_reviewed_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_bdo_reviewer_user",
        "borrower_debt_obligations",
        "users",
        ["last_reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE borrower_debt_obligations
        SET installment_amount = COALESCE(monthly_installment, 0),
            installment_frequency = 'monthly',
            total_installments = remaining_term_months,
            remaining_installments = remaining_term_months,
            status = CASE
                WHEN COALESCE(current_balance, 0) <= 0 THEN 'settled'
                ELSE 'active'
            END
        """
    )

    op.create_table(
        "borrower_debt_obligation_events",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=40), server_default="reviewed", nullable=False),
        sa.Column("event_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("balance_after", sa.Numeric(15, 2), nullable=True),
        sa.Column("remaining_installments_after", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["obligation_id"], ["borrower_debt_obligations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bdoe_company", "borrower_debt_obligation_events", ["company_id"], unique=False)
    op.create_index("ix_bdoe_borrower", "borrower_debt_obligation_events", ["borrower_id"], unique=False)
    op.create_index("ix_bdoe_obligation", "borrower_debt_obligation_events", ["obligation_id"], unique=False)
    op.create_index("ix_bdoe_recorder", "borrower_debt_obligation_events", ["recorded_by_user_id"], unique=False)
    op.create_index("ix_bdoe_type", "borrower_debt_obligation_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bdoe_type", table_name="borrower_debt_obligation_events")
    op.drop_index("ix_bdoe_recorder", table_name="borrower_debt_obligation_events")
    op.drop_index("ix_bdoe_obligation", table_name="borrower_debt_obligation_events")
    op.drop_index("ix_bdoe_borrower", table_name="borrower_debt_obligation_events")
    op.drop_index("ix_bdoe_company", table_name="borrower_debt_obligation_events")
    op.drop_table("borrower_debt_obligation_events")

    op.drop_constraint("fk_bdo_reviewer_user", "borrower_debt_obligations", type_="foreignkey")
    op.drop_index("ix_bdo_reviewer", table_name="borrower_debt_obligations")
    op.drop_index("ix_bdo_status", table_name="borrower_debt_obligations")
    op.drop_column("borrower_debt_obligations", "notes")
    op.drop_column("borrower_debt_obligations", "last_reviewed_by_user_id")
    op.drop_column("borrower_debt_obligations", "last_reviewed_at")
    op.drop_column("borrower_debt_obligations", "status")
    op.drop_column("borrower_debt_obligations", "next_due_date")
    op.drop_column("borrower_debt_obligations", "remaining_installments")
    op.drop_column("borrower_debt_obligations", "installments_paid")
    op.drop_column("borrower_debt_obligations", "total_installments")
    op.drop_column("borrower_debt_obligations", "installment_frequency")
    op.drop_column("borrower_debt_obligations", "installment_amount")
    op.drop_column("borrower_debt_obligations", "started_on")
