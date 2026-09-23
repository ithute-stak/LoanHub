"""Durable CDAS daily intelligence runs

Revision ID: f9x3y5z7a250
Revises: e8w2x4y6z249
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f9x3y5z7a250"
down_revision: Union[str, Sequence[str], None] = "e8w2x4y6z249"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cdas_daily_intelligence_runs",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("scheduled_time", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("max_profiles", sa.Integer(), nullable=False),
        sa.Column("eligible_profiles", sa.Integer(), nullable=False),
        sa.Column("checked_profiles", sa.Integer(), nullable=False),
        sa.Column("ready_profiles", sa.Integer(), nullable=False),
        sa.Column("no_capacity_profiles", sa.Integer(), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("provider_writes", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "run_date",
            name="uq_cdas_daily_intelligence_company_date",
        ),
    )
    op.create_index(
        op.f("ix_cdas_daily_intelligence_runs_company_id"),
        "cdas_daily_intelligence_runs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cdas_daily_intelligence_runs_run_date"),
        "cdas_daily_intelligence_runs",
        ["run_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cdas_daily_intelligence_runs_status"),
        "cdas_daily_intelligence_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cdas_daily_intelligence_runs_status"), table_name="cdas_daily_intelligence_runs")
    op.drop_index(op.f("ix_cdas_daily_intelligence_runs_run_date"), table_name="cdas_daily_intelligence_runs")
    op.drop_index(op.f("ix_cdas_daily_intelligence_runs_company_id"), table_name="cdas_daily_intelligence_runs")
    op.drop_table("cdas_daily_intelligence_runs")
