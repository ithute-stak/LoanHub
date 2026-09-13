"""add CDAS booking monitoring

Revision ID: b1q5s7t9u023
Revises: a0p4r6s8t910
Create Date: 2026-09-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1q5s7t9u023"
down_revision: Union[str, Sequence[str], None] = "a0p4r6s8t910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cdas_booking_monitors",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("client_reference", sa.String(length=120), nullable=True),
        sa.Column("item_code", sa.String(length=80), nullable=False),
        sa.Column("agency_name", sa.String(length=255), nullable=False),
        sa.Column("deduction_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("reference_no", sa.String(length=255), nullable=True),
        sa.Column("source_status", sa.String(length=80), nullable=False, server_default="Active"),
        sa.Column("booking_lead_months", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("booking_open_date", sa.Date(), nullable=False),
        sa.Column("alert_start_date", sa.Date(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booked_at", sa.DateTime(), nullable=True),
        sa.Column("booked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["booked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id", "client_name", "client_reference", "agency_name", "expiry_date",
        "reference_no", "booking_open_date", "alert_start_date", "created_by_user_id",
        "booked_at", "booked_by_user_id",
    ):
        op.create_index(f"ix_cdas_booking_monitors_{column}", "cdas_booking_monitors", [column], unique=False)


def downgrade() -> None:
    op.drop_table("cdas_booking_monitors")
