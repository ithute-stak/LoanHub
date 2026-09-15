"""Add CDAS contact/follow-up management.

Revision ID: e5t9u1v3w028
Revises: d4s8t0u2v027
Create Date: 2026-09-15

Adds opportunity assignment and an append-only company-scoped contact activity table.
Existing CDAS data is retained unchanged.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5t9u1v3w028"
down_revision = "d4s8t0u2v027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cdas_booking_opportunities",
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cdas_booking_opportunities_assigned_to_user_id_users",
        "cdas_booking_opportunities",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_cdas_booking_opportunities_assigned_to_user_id",
        "cdas_booking_opportunities",
        ["assigned_to_user_id"],
        unique=False,
    )

    op.create_table(
        "cdas_opportunity_contacts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("contacted_at", sa.DateTime(), nullable=False),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
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
        "channel",
        "outcome",
        "contacted_at",
        "next_follow_up_at",
        "created_by_user_id",
    ):
        op.create_index(
            f"ix_cdas_opportunity_contacts_{column}",
            "cdas_opportunity_contacts",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("cdas_opportunity_contacts")
    op.drop_index(
        "ix_cdas_booking_opportunities_assigned_to_user_id",
        table_name="cdas_booking_opportunities",
    )
    op.drop_constraint(
        "fk_cdas_booking_opportunities_assigned_to_user_id_users",
        "cdas_booking_opportunities",
        type_="foreignkey",
    )
    op.drop_column("cdas_booking_opportunities", "assigned_to_user_id")
