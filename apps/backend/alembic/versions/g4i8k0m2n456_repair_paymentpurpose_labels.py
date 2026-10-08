"""Repair PaymentPurpose enum labels used by current SQLAlchemy enum.

Revision ID: g4i8k0m2n456
Revises: f3h7j9l1m345
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "g4i8k0m2n456"
down_revision: Union[str, Sequence[str], None] = "f3h7j9l1m345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PaymentTransaction.purpose uses SQLAlchemy Enum(PaymentPurpose), which
    # persists enum member names. Historical migration c4f9e2d7a110 added
    # lowercase labels for these newer values, leaving production databases
    # unable to bind DIRECT_DEBIT and related members.
    for label in (
        "BORROW_REQUEST_FEE",
        "PLATFORM_TRANSACTION_CHARGE",
        "PLATFORM_CLAIM_SETTLEMENT",
        "DIRECT_DEBIT",
    ):
        op.execute(f"ALTER TYPE paymentpurpose ADD VALUE IF NOT EXISTS '{label}'")


def downgrade() -> None:
    # PostgreSQL enum labels are append-only for safe rolling compatibility.
    pass
