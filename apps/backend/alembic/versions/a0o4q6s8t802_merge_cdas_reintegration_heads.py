"""Merge CDAS reintegration migration heads.

Revision ID: a0o4q6s8t802
Revises: a0o4q6s8t801, e9x3y5z7a250
Create Date: 2026-09-25

This is a structural Alembic merge revision. Both parent migrations contain
independent schema changes, so no additional DDL is required here.
"""

from typing import Sequence, Union


revision: str = "a0o4q6s8t802"
down_revision: Union[str, Sequence[str], None] = (
    "a0o4q6s8t801",
    "e9x3y5z7a250",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
