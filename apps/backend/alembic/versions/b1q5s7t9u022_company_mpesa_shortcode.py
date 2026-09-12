"""add company M-Pesa shortcode

Revision ID: b1q5s7t9u022
Revises: q1c4e7g0h016
Create Date: 2026-08-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1q5s7t9u022"
down_revision: Union[str, Sequence[str], None] = "q1c4e7g0h016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "loan_companies",
        sa.Column("mpesa_shortcode", sa.String(length=12), nullable=True),
    )
    op.create_index(
        "ix_loan_companies_mpesa_shortcode",
        "loan_companies",
        ["mpesa_shortcode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_loan_companies_mpesa_shortcode", table_name="loan_companies")
    op.drop_column("loan_companies", "mpesa_shortcode")
