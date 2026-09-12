"""Add verified company M-Pesa settlement destination.

Revision ID: k1a5c7d9e011
Revises: j0z4b6c8e910
"""

import sqlalchemy as sa
from alembic import op


revision = "k1a5c7d9e011"
down_revision = "j0z4b6c8e910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "loan_companies",
        sa.Column("settlement_provider", sa.String(length=30), server_default="mpesa", nullable=False),
    )
    op.add_column(
        "loan_companies",
        sa.Column("settlement_shortcode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "loan_companies",
        sa.Column("settlement_currency", sa.String(length=3), server_default="LSL", nullable=False),
    )
    op.add_column(
        "loan_companies",
        sa.Column("settlement_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "loan_companies",
        sa.Column("settlement_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "loan_companies",
        sa.Column("settlement_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("loan_companies", "settlement_verified_at")
    op.drop_column("loan_companies", "settlement_verified")
    op.drop_column("loan_companies", "settlement_enabled")
    op.drop_column("loan_companies", "settlement_currency")
    op.drop_column("loan_companies", "settlement_shortcode")
    op.drop_column("loan_companies", "settlement_provider")
