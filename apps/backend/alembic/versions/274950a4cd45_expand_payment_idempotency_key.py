"""legacy migration-chain compatibility marker

Revision ID: 274950a4cd45
Revises: 46b05ea64319

The original autogenerate output mixed unrelated index, JSON and foreign-key
changes into the idempotency-key correction. Those unsafe operations were
removed. The next migration defensively verifies the required schema so this
revision remains compatible with databases that already recorded its ID.
"""

from typing import Sequence, Union

revision: str = "274950a4cd45"
down_revision: Union[str, Sequence[str], None] = "46b05ea64319"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
