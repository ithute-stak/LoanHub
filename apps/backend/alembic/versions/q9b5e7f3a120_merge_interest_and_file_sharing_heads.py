"""merge interest-method and file-sharing migration branches

Revision ID: q9b5e7f3a120
Revises: n7f2d4c8b610, p8a4d6e2f910
Create Date: 2026-07-23

This is a merge-only migration. It performs no schema changes; it joins the
interest-method and file-sharing branches into one Alembic head.
"""

from typing import Sequence, Union


revision: str = "q9b5e7f3a120"
down_revision: Union[str, Sequence[str], None] = (
    "n7f2d4c8b610",
    "p8a4d6e2f910",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the two branches; no database objects need to be changed."""


def downgrade() -> None:
    """Splitting a merge revision requires no database object changes."""
