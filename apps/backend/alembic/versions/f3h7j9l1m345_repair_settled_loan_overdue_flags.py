"""Repair stale current-overdue flags on settled loans.

Revision ID: f3h7j9l1m345
Revises: e2g6i8k0l234
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f3h7j9l1m345"
down_revision: Union[str, Sequence[str], None] = "e2g6i8k0l234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE client_company_loan
        SET is_overdue = FALSE
        WHERE is_overdue = TRUE
          AND balance <= 0
        """
    )


def downgrade() -> None:
    pass
