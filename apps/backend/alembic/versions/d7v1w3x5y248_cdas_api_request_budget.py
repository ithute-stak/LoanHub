"""CDAS API daily request budget

Revision ID: d7v1w3x5y248
Revises: c6u0v2w4x247
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d7v1w3x5y248"
down_revision: Union[str, Sequence[str], None] = "c6u0v2w4x247"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cdas_api_request_budgets",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_key", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_request_at", sa.DateTime(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_key",
            "environment",
            "request_date",
            name="uq_cdas_api_budget_account_env_date",
        ),
    )
    op.create_index("ix_cdas_api_request_budgets_company_id", "cdas_api_request_budgets", ["company_id"])
    op.create_index("ix_cdas_api_request_budgets_account_key", "cdas_api_request_budgets", ["account_key"])
    op.create_index("ix_cdas_api_request_budgets_environment", "cdas_api_request_budgets", ["environment"])
    op.create_index("ix_cdas_api_request_budgets_request_date", "cdas_api_request_budgets", ["request_date"])


def downgrade() -> None:
    op.drop_table("cdas_api_request_budgets")
