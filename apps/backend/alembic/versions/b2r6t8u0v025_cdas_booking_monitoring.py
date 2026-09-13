"""Persist CDAS booking monitoring opportunities.

Revision ID: b2r6t8u0v025
Revises: b2c3d4e5f912
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2r6t8u0v025"
down_revision = "b2c3d4e5f912"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cdas_booking_opportunities",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("client_reference", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="monitoring"),
        sa.Column("booking_lead_months", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("alert_lead_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("booking_open_date", sa.Date(), nullable=True),
        sa.Column("alert_start_date", sa.Date(), nullable=True),
        sa.Column("opportunity_agency_name", sa.String(length=255), nullable=True),
        sa.Column("opportunity_item_code", sa.String(length=100), nullable=True),
        sa.Column("opportunity_reference_no", sa.String(length=255), nullable=True),
        sa.Column("opportunity_effective_date", sa.Date(), nullable=True),
        sa.Column("opportunity_expiry_date", sa.Date(), nullable=True),
        sa.Column("opportunity_deduction_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_monthly_deductions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("own_monthly_deductions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("competitor_monthly_deductions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("analysis_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("booked_at", sa.DateTime(), nullable=True),
        sa.Column("booked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "client_name",
        "client_reference",
        "status",
        "booking_open_date",
        "alert_start_date",
        "opportunity_reference_no",
        "booked_by_user_id",
    ):
        op.create_index(
            f"ix_cdas_booking_opportunities_{column}",
            "cdas_booking_opportunities",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("cdas_booking_opportunities")
