"""Repair stale current-overdue flags on settled loans.

Revision ID: b0p5r7t9u803
Revises: a0o4q6s8t802
Create Date: 2026-09-25

Historical late-payment evidence remains in repayment installments and payment
history. This migration only clears the *current* loan-level overdue flag where
there is no outstanding balance.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b0p5r7t9u803"
down_revision: Union[str, Sequence[str], None] = "a0o4q6s8t802"
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
    # Intentionally irreversible: the previous flag was stale current-state
    # data, and historical delinquency remains available from repayment history.
    pass
