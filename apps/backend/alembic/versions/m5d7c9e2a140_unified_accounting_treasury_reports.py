"""unified accounting treasury reports

Revision ID: m5d7c9e2a140
Revises: k3f1a6b8c240
Create Date: 2026-07-21 20:30:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m5d7c9e2a140"
down_revision = "k3f1a6b8c240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branch_daily_submissions",
        sa.Column("pdf_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_branch_daily_submission_pdf_file",
        "branch_daily_submissions",
        "managed_files",
        ["pdf_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_branch_daily_submissions_pdf_file_id",
        "branch_daily_submissions",
        ["pdf_file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_branch_daily_submissions_pdf_file_id", table_name="branch_daily_submissions")
    op.drop_constraint("fk_branch_daily_submission_pdf_file", "branch_daily_submissions", type_="foreignkey")
    op.drop_column("branch_daily_submissions", "pdf_file_id")
