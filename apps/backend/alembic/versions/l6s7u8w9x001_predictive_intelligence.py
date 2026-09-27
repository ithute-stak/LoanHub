"""add predictive intelligence

Revision ID: l6s7u8w9x001
Revises: k5r6t7v8w901
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "l6s7u8w9x001"
down_revision = "k5r6t7v8w901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "predictive_intelligence_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_scope_key", sa.String(length=40), server_default="ALL", nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("source_snapshot_date", sa.Date(), nullable=False),
        sa.Column("previous_snapshot_date", sa.Date(), nullable=True),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=40), server_default="on_demand", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("model_version", sa.String(length=80), server_default="transparent-rules-v1", nullable=False),
        sa.Column("lookback_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("loan_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stable_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("watch_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("elevated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("high_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("critical_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("projected_par30_entry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observed_collection_rate", sa.Numeric(8, 4), server_default="0", nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "as_of_date", "branch_scope_key", name="uq_predictive_run_company_date_scope"),
        sa.UniqueConstraint("run_reference"),
    )
    for column in ("company_id", "branch_id", "as_of_date", "source_snapshot_date", "previous_snapshot_date", "run_reference", "run_type", "status"):
        op.create_index(f"ix_predictive_intelligence_runs_{column}", "predictive_intelligence_runs", [column])

    op.create_table(
        "predictive_loan_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_number", sa.String(length=40), nullable=False),
        sa.Column("loan_reference", sa.String(length=80), nullable=True),
        sa.Column("risk_score", sa.Numeric(6, 2), server_default="0", nullable=False),
        sa.Column("risk_band", sa.String(length=30), server_default="stable", nullable=False),
        sa.Column("current_dpd", sa.Integer(), server_default="0", nullable=False),
        sa.Column("previous_dpd", sa.Integer(), nullable=True),
        sa.Column("dpd_change", sa.Integer(), nullable=True),
        sa.Column("current_bucket", sa.String(length=30), nullable=False),
        sa.Column("previous_bucket", sa.String(length=30), nullable=True),
        sa.Column("first_payment_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("projected_par30_entry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("stress_bucket_30d", sa.String(length=30), nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("rationale", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_predictive_signal_score"),
        sa.CheckConstraint("risk_band IN ('stable','watch','elevated','high','critical')", name="ck_predictive_signal_band"),
        sa.ForeignKeyConstraint(["run_id"], ["predictive_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "loan_id", name="uq_predictive_signal_run_loan"),
    )
    for column in ("run_id", "company_id", "branch_id", "loan_id", "borrower_id", "folio_number", "loan_reference", "risk_score", "risk_band", "projected_par30_entry"):
        op.create_index(f"ix_predictive_loan_signals_{column}", "predictive_loan_signals", [column])

    op.create_table(
        "predictive_cashflow_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("contractual_due", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("expected_collection", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("observed_collection_rate", sa.Numeric(8, 4), server_default="0", nullable=False),
        sa.Column("due_installment_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("history_installment_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("confidence_band", sa.String(length=20), server_default="low", nullable=False),
        sa.Column("method", sa.String(length=60), server_default="contractual_no_history", nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("horizon_days IN (30,60,90)", name="ck_predictive_cashflow_horizon"),
        sa.CheckConstraint("observed_collection_rate >= 0 AND observed_collection_rate <= 1", name="ck_predictive_cashflow_rate"),
        sa.ForeignKeyConstraint(["run_id"], ["predictive_intelligence_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "horizon_days", name="uq_predictive_cashflow_run_horizon"),
    )
    for column in ("run_id", "company_id", "branch_id", "horizon_days"):
        op.create_index(f"ix_predictive_cashflow_forecasts_{column}", "predictive_cashflow_forecasts", [column])


def downgrade() -> None:
    op.drop_table("predictive_cashflow_forecasts")
    op.drop_table("predictive_loan_signals")
    op.drop_table("predictive_intelligence_runs")
