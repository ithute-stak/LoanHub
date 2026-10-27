"""Record first reconciliation requirement for CDAS provider operations.

Revision ID: c7d2h4s6t821
Revises: c7d2h4s6t820
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d2h4s6t821"
down_revision = "c7d2h4s6t820"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cdas_provider_operations",
        sa.Column("reconciliation_required_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("cdas_provider_operations", "reconciliation_required_at")
