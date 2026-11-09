"""Record borrower-account affirmation separately from physical Wacom signing.

Revision ID: a2b3c4d5e734
Revises: f1a2b3c4d623
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "a2b3c4d5e734"
down_revision = "f1a2b3c4d623"
branch_labels = None
depends_on = None


def upgrade():
    table = "wacom_execution_ceremony_challenges"
    op.add_column(table, sa.Column("borrower_affirmed_at", sa.DateTime(timezone=True)))
    op.add_column(table, sa.Column(
        "borrower_affirmed_user_id", UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
    ))
    op.add_column(table, sa.Column("borrower_affirmation_sha256", sa.String(64)))
    op.create_check_constraint(
        "ck_wacom_ceremony_borrower_affirmation_complete", table,
        "(borrower_affirmed_at IS NULL AND borrower_affirmed_user_id IS NULL "
        "AND borrower_affirmation_sha256 IS NULL) OR "
        "(borrower_affirmed_at IS NOT NULL AND borrower_affirmed_user_id IS NOT NULL "
        "AND length(borrower_affirmation_sha256) = 64)",
    )


def downgrade():
    table = "wacom_execution_ceremony_challenges"
    op.drop_constraint("ck_wacom_ceremony_borrower_affirmation_complete", table, type_="check")
    op.drop_column(table, "borrower_affirmation_sha256")
    op.drop_column(table, "borrower_affirmed_user_id")
    op.drop_column(table, "borrower_affirmed_at")
