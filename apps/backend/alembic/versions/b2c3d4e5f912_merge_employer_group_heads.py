"""merge employer-group migration with the active LoanHub migration head

Revision ID: b2c3d4e5f912
Revises: a1b2c3d4e910, a1p5r7t9u913
Create Date: 2026-09-08
"""

from typing import Sequence, Union

revision: str = "b2c3d4e5f912"
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e910', 'a1p5r7t9u913')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration branches; schema changes live in the parent revisions."""
    pass


def downgrade() -> None:
    """Split the merge point without reverting either parent branch."""
    pass
