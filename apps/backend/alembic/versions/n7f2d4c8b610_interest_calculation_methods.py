"""add configurable interest calculation method to loan products

Revision ID: n7f2d4c8b610
Revises: m5d7c9e2a140
Create Date: 2026-07-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "n7f2d4c8b610"
down_revision: Union[str, Sequence[str], None] = "m5d7c9e2a140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "loan_products",
        sa.Column(
            "interest_method",
            sa.String(length=50),
            nullable=False,
            server_default="micro_loan",
        ),
    )
    op.create_index(
        "ix_loan_products_interest_method",
        "loan_products",
        ["interest_method"],
        unique=False,
    )
    op.alter_column("loan_products", "interest_method", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_loan_products_interest_method", table_name="loan_products")
    op.drop_column("loan_products", "interest_method")
