"""Add append-only CDAS booking failure tracking.

Revision ID: f6u0v2w4x029
Revises: e5t9u1v3w028
Create Date: 2026-09-15

Adds a company-scoped failure-attempt table. Existing CDAS opportunities,
contacts and analysis history remain unchanged.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6u0v2w4x029"
down_revision = "e5t9u1v3w028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cdas_booking_failures",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("reason_details", sa.Text(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=False),
        sa.Column("retry_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retry_after", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["cdas_booking_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "opportunity_id",
        "reason_code",
        "failed_at",
        "retry_eligible",
        "retry_after",
        "created_by_user_id",
    ):
        op.create_index(
            f"ix_cdas_booking_failures_{column}",
            "cdas_booking_failures",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("cdas_booking_failures")
