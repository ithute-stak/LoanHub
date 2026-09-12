"""Merge active Alembic heads after legacy cash-out register.

Revision ID: s5e1a7b3c018
Revises: d6w9x3y4z357, r4d8f0a2b017
Create Date: 2026-08-21

Both predecessor revisions contain independent schema changes already represented
in the repository. This revision intentionally performs no DDL; it only restores
one unambiguous Alembic upgrade target.
"""


revision = "s5e1a7b3c018"
down_revision = ("d6w9x3y4z357", "r4d8f0a2b017")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
