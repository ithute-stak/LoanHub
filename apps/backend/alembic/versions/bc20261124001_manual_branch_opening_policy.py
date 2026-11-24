"""Default branch daily opening balances to manual entry.

Revision ID: bc20261124001
Revises: dc20261122002

Existing opening source records and submitted day totals are not changed.
The new setting affects only future automatic carry-forward behaviour.
"""
from alembic import op
import sqlalchemy as sa

revision = "bc20261124001"
down_revision = "dc20261122002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "treasury_settings",
        sa.Column(
            "carry_previous_closing_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("treasury_settings", "carry_previous_closing_enabled")
