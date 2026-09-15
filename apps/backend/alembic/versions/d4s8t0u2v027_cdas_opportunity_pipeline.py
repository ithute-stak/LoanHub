"""Add persistent CDAS opportunity pipeline fields.

Revision ID: d4s8t0u2v027
Revises: c3r7t9u1v026
Create Date: 2026-09-15

This migration is additive. Existing opportunities are retained and backfilled to
Identified or Booked according to their current status.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4s8t0u2v027"
down_revision = "c3r7t9u1v026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cdas_booking_opportunities",
        sa.Column("pipeline_stage", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "cdas_booking_opportunities",
        sa.Column("pipeline_updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "cdas_booking_opportunities",
        sa.Column(
            "pipeline_updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_cdas_booking_opportunities_pipeline_updated_by_user_id_users",
        "cdas_booking_opportunities",
        "users",
        ["pipeline_updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE cdas_booking_opportunities
        SET pipeline_stage = CASE
            WHEN status = 'booked' THEN 'booked'
            ELSE 'identified'
        END,
        pipeline_updated_at = CASE
            WHEN status = 'booked' AND booked_at IS NOT NULL THEN booked_at
            ELSE COALESCE(updated_at, created_at, now())
        END,
        pipeline_updated_by_user_id = CASE
            WHEN status = 'booked' THEN booked_by_user_id
            ELSE NULL
        END
    """))

    op.alter_column(
        "cdas_booking_opportunities",
        "pipeline_stage",
        existing_type=sa.String(length=40),
        nullable=False,
        server_default="identified",
    )
    op.create_index(
        "ix_cdas_booking_opportunities_pipeline_stage",
        "cdas_booking_opportunities",
        ["pipeline_stage"],
        unique=False,
    )
    op.create_index(
        "ix_cdas_booking_opportunities_pipeline_updated_by_user_id",
        "cdas_booking_opportunities",
        ["pipeline_updated_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cdas_booking_opportunities_pipeline_updated_by_user_id",
        table_name="cdas_booking_opportunities",
    )
    op.drop_index(
        "ix_cdas_booking_opportunities_pipeline_stage",
        table_name="cdas_booking_opportunities",
    )
    op.drop_constraint(
        "fk_cdas_booking_opportunities_pipeline_updated_by_user_id_users",
        "cdas_booking_opportunities",
        type_="foreignkey",
    )
    op.drop_column("cdas_booking_opportunities", "pipeline_updated_by_user_id")
    op.drop_column("cdas_booking_opportunities", "pipeline_updated_at")
    op.drop_column("cdas_booking_opportunities", "pipeline_stage")
