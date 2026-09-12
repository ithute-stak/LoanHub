"""manual installment due dates

Revision ID: w6h8j0k2m470
Revises: v5g7c9d2e460
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "w6h8j0k2m470"
down_revision: str = "v5g7c9d2e460"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "direct_loan_applications",
        sa.Column(
            "installment_due_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column(
        "direct_loan_applications",
        "installment_due_dates",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("direct_loan_applications", "installment_due_dates")
