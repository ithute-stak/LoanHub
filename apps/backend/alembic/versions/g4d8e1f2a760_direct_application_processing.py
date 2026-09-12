"""Direct application review and decision audit fields.

Revision ID: g4d8e1f2a760
Revises: f2c6a8e1d430
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g4d8e1f2a760"
down_revision = "f2c6a8e1d430"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("direct_loan_applications", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "direct_loan_applications",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("direct_loan_applications", sa.Column("decision_notes", sa.Text(), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column(
        "direct_loan_applications",
        sa.Column("rejected_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_direct_applications_reviewed_by",
        "direct_loan_applications",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_direct_applications_rejected_by",
        "direct_loan_applications",
        "users",
        ["rejected_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_direct_loan_applications_reviewed_by_user_id",
        "direct_loan_applications",
        ["reviewed_by_user_id"],
    )
    op.create_index(
        "ix_direct_loan_applications_rejected_by_user_id",
        "direct_loan_applications",
        ["rejected_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_direct_loan_applications_rejected_by_user_id", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_reviewed_by_user_id", table_name="direct_loan_applications")
    op.drop_constraint("fk_direct_applications_rejected_by", "direct_loan_applications", type_="foreignkey")
    op.drop_constraint("fk_direct_applications_reviewed_by", "direct_loan_applications", type_="foreignkey")
    op.drop_column("direct_loan_applications", "rejected_by_user_id")
    op.drop_column("direct_loan_applications", "rejected_at")
    op.drop_column("direct_loan_applications", "decision_notes")
    op.drop_column("direct_loan_applications", "reviewed_by_user_id")
    op.drop_column("direct_loan_applications", "reviewed_at")
