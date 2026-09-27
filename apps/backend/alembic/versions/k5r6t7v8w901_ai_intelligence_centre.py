"""add explainable AI intelligence centre

Revision ID: k5r6t7v8w901
Revises: j4q5s6u7v801
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "k5r6t7v8w901"
down_revision = "j4q5s6u7v801"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_intelligence_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=40), server_default="on_demand", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="running", nullable=False),
        sa.Column("model_version", sa.String(length=80), server_default="explainable-v1", nullable=False),
        sa.Column("evidence_cutoff_at", sa.DateTime(), nullable=False),
        sa.Column("insight_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("critical_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("high_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("medium_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("low_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "run_reference", name="uq_ai_intelligence_run_reference"),
    )
    for column in ("company_id", "branch_id", "run_reference", "run_type", "status"):
        op.create_index(f"ix_ai_intelligence_runs_{column}", "ai_intelligence_runs", [column])

    op.create_table(
        "ai_intelligence_insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("insight_type", sa.String(length=60), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("confidence_percent", sa.Numeric(6, 2), server_default="0", nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("folio_number", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("rationale", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("feedback", sa.String(length=30), nullable=True),
        sa.Column("feedback_note", sa.Text(), nullable=True),
        sa.CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_ai_intelligence_insight_severity"),
        sa.CheckConstraint("status IN ('open','reviewed','dismissed','actioned')", name="ck_ai_intelligence_insight_status"),
        sa.CheckConstraint("confidence_percent >= 0 AND confidence_percent <= 100", name="ck_ai_intelligence_insight_confidence"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "fingerprint", name="uq_ai_intelligence_run_fingerprint"),
    )
    for column in ("run_id", "company_id", "branch_id", "insight_type", "domain", "severity", "entity_type", "entity_id", "folio_number", "status"):
        op.create_index(f"ix_ai_intelligence_insights_{column}", "ai_intelligence_insights", [column])

    op.create_table(
        "ai_intelligence_guardrail_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insight_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["insight_id"], ["ai_intelligence_insights.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "insight_id", "event_type"):
        op.create_index(f"ix_ai_intelligence_guardrail_events_{column}", "ai_intelligence_guardrail_events", [column])


def downgrade() -> None:
    op.drop_table("ai_intelligence_guardrail_events")
    op.drop_table("ai_intelligence_insights")
    op.drop_table("ai_intelligence_runs")
