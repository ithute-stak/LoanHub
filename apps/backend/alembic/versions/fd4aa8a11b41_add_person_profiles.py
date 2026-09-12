"""add person profiles

Revision ID: fd4aa8a11b41
Revises: af6a1575fb01
Create Date: 2026-07-13 17:46:48.524568

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'fd4aa8a11b41'
down_revision: Union[str, Sequence[str], None] = 'af6a1575fb01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
