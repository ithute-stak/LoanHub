"""Link LoanHub users to centralized !thute Auth identities.

Revision ID: a1p5r7t9u913
Revises: s5e1a7b3c018
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1p5r7t9u913"
down_revision: Union[str, Sequence[str], None] = "s5e1a7b3c018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_users_auth_user_id",
        "users",
        ["auth_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_auth_user_id", table_name="users")
    op.drop_column("users", "auth_user_id")
