"""add missing LoanHub Money payment-purpose label

Revision ID: c5u8v2w3x246
Revises: c4t7u9v1w245
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5u8v2w3x246"
down_revision: Union[str, Sequence[str], None] = "c4t7u9v1w245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy persists PaymentPurpose enum member names. The application
    # already uses BUSINESS_PAYMENT; existing databases need this label too.
    op.execute(
        "ALTER TYPE paymentpurpose ADD VALUE IF NOT EXISTS 'BUSINESS_PAYMENT'"
    )


def downgrade() -> None:
    # PostgreSQL enum labels cannot be safely removed in place.
    pass
