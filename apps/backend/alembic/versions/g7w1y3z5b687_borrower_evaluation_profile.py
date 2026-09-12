"""richer borrower evaluation profile

Revision ID: g7w1y3z5b687
Revises: f6v0x2z4a576
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7w1y3z5b687"
down_revision: Union[str, Sequence[str], None] = "f6v0x2z4a576"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("borrowers", sa.Column("employment_type", sa.String(length=50), nullable=True))
    op.add_column("borrowers", sa.Column("employment_start_date", sa.Date(), nullable=True))
    op.add_column("borrowers", sa.Column("net_monthly_income", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "borrowers",
        sa.Column("other_monthly_income", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column("borrowers", sa.Column("other_income_source", sa.String(length=200), nullable=True))
    op.add_column(
        "borrowers",
        sa.Column("monthly_living_expenses", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "borrowers",
        sa.Column("monthly_debt_repayments", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "borrowers",
        sa.Column("dependants", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("borrowers", sa.Column("residential_status", sa.String(length=40), nullable=True))
    op.add_column("borrowers", sa.Column("years_at_address", sa.Integer(), nullable=True))
    op.add_column("borrowers", sa.Column("bank_name", sa.String(length=120), nullable=True))
    op.add_column("borrowers", sa.Column("account_holder_name", sa.String(length=200), nullable=True))
    op.add_column("borrowers", sa.Column("account_last_four", sa.String(length=4), nullable=True))
    op.add_column(
        "borrowers",
        sa.Column(
            "consent_to_share_documents",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_borrowers_evaluation_amounts_nonnegative",
        "borrowers",
        "coalesce(net_monthly_income, 0) >= 0 AND other_monthly_income >= 0 "
        "AND monthly_living_expenses >= 0 AND monthly_debt_repayments >= 0",
    )
    op.create_check_constraint(
        "ck_borrowers_dependants_nonnegative",
        "borrowers",
        "dependants >= 0",
    )
    op.create_check_constraint(
        "ck_borrowers_years_at_address_nonnegative",
        "borrowers",
        "years_at_address IS NULL OR years_at_address >= 0",
    )
    op.create_check_constraint(
        "ck_borrowers_account_last_four",
        "borrowers",
        "account_last_four IS NULL OR account_last_four ~ '^[0-9]{4}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_borrowers_account_last_four", "borrowers", type_="check")
    op.drop_constraint("ck_borrowers_years_at_address_nonnegative", "borrowers", type_="check")
    op.drop_constraint("ck_borrowers_dependants_nonnegative", "borrowers", type_="check")
    op.drop_constraint("ck_borrowers_evaluation_amounts_nonnegative", "borrowers", type_="check")

    for column in [
        "consent_to_share_documents",
        "account_last_four",
        "account_holder_name",
        "bank_name",
        "years_at_address",
        "residential_status",
        "dependants",
        "monthly_debt_repayments",
        "monthly_living_expenses",
        "other_income_source",
        "other_monthly_income",
        "net_monthly_income",
        "employment_start_date",
        "employment_type",
    ]:
        op.drop_column("borrowers", column)
