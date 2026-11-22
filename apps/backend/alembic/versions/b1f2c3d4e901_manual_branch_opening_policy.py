"""Stage manual-by-default branch opening mode.

Revision ID: b1f2c3d4e901
Revises: z9n3p5q7r800

This migration only adds configuration. It deliberately does not delete or
rewrite existing branch opening sources or submitted financial statements.
"""
from alembic import op
import sqlalchemy as sa

revision = "b1f2c3d4e901"
down_revision = "z9n3p5q7r800"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "treasury_settings",
        sa.Column(
            "opening_balance_mode",
            sa.String(length=24),
            nullable=False,
            server_default="manual",
        ),
    )
    op.create_check_constraint(
        "ck_treasury_settings_opening_balance_mode",
        "treasury_settings",
        "opening_balance_mode IN ('manual', 'previous_closing')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_treasury_settings_opening_balance_mode",
        "treasury_settings",
        type_="check",
    )
    op.drop_column("treasury_settings", "opening_balance_mode")
