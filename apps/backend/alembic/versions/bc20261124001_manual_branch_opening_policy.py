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
            server_default=sa.text("true"),
        ),
    )
    # Preserve each existing company's currently active carry-forward policy.
    # Newly created treasury settings default to manual opening; existing
    # companies require an explicit migration to the new rule.
    op.alter_column(
        "treasury_settings", "carry_previous_closing_enabled",
        server_default=sa.text("false"),
    )
    op.add_column(
        "treasury_settings",
        sa.Column(
            "enforce_branch_cash_controls_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("treasury_settings", "enforce_branch_cash_controls_enabled")
    op.drop_column("treasury_settings", "carry_previous_closing_enabled")
