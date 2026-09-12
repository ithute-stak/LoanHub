"""compatibility marker for an already-recorded local revision

Revision ID: 3957062b7c66
Revises: 6c1f9a7e2d40

Some installations recorded this revision before the generated file was
removed.  It is intentionally retained as a no-op so all existing databases
can resolve their history without repeating the accidental schema changes.
The canonical schema repair is performed by b84d1f2a9c30.
"""

from typing import Sequence, Union


revision: str = "3957062b7c66"
down_revision: Union[str, Sequence[str], None] = "6c1f9a7e2d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
