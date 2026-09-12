"""expand payment idempotency key

Revision ID: 46b05ea64319
Revises: 307dcdf0187c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "46b05ea64319"
down_revision: Union[str, Sequence[str], None] = "307dcdf0187c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payment_transactions",
        "idempotency_key",
        existing_type=sa.String(length=120),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "payment_transactions",
        "idempotency_key",
        existing_type=sa.String(length=255),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
