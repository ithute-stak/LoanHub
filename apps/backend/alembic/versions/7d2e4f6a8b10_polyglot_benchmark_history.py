"""persist polyglot benchmark promotion evidence

Revision ID: 7d2e4f6a8b10
Revises: r1x2z3b4c501
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "7d2e4f6a8b10"
down_revision = "r1x2z3b4c501"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polyglot_benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("all_candidates", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("promotion_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("routing_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_polyglot_benchmark_runs_requested_by_user_id"),
        "polyglot_benchmark_runs",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_polyglot_benchmark_runs_all_candidates"),
        "polyglot_benchmark_runs",
        ["all_candidates"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_polyglot_benchmark_runs_all_candidates"),
        table_name="polyglot_benchmark_runs",
    )
    op.drop_index(
        op.f("ix_polyglot_benchmark_runs_requested_by_user_id"),
        table_name="polyglot_benchmark_runs",
    )
    op.drop_table("polyglot_benchmark_runs")
