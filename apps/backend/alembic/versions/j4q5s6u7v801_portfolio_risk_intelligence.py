"""add portfolio risk intelligence

Revision ID: j4q5s6u7v801
Revises: i3p4r5t6u702
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "j4q5s6u7v801"
down_revision = "i3p4r5t6u702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_risk_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employer_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("origination_month", sa.Date(), nullable=True),
        sa.Column("days_past_due", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delinquency_bucket", sa.String(length=30), server_default="current", nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("overdue_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("principal_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("installment_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("loan_status", sa.String(length=30), nullable=False),
        sa.Column("origination_channel", sa.String(length=30), server_default="unknown", nullable=False),
        sa.Column("collection_channel", sa.String(length=40), server_default="direct", nullable=False),
        sa.Column("product_label", sa.String(length=180), server_default="Unmapped product", nullable=False),
        sa.Column("employer_label", sa.String(length=220), server_default="No employer group", nullable=False),
        sa.Column("branch_label", sa.String(length=180), server_default="Unassigned branch", nullable=False),
        sa.Column("is_top_up", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("first_payment_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_written_off", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cdas_collection_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("days_past_due >= 0", name="ck_portfolio_risk_snapshot_dpd"),
        sa.CheckConstraint("outstanding_balance >= 0", name="ck_portfolio_risk_snapshot_balance"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employer_group_id"], ["employer_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["loan_products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "snapshot_date", "loan_id", name="uq_portfolio_risk_snapshot_company_date_loan"),
    )
    for name, cols in (
        ("ix_portfolio_risk_snapshots_company_id", ["company_id"]),
        ("ix_portfolio_risk_snapshots_branch_id", ["branch_id"]),
        ("ix_portfolio_risk_snapshots_loan_id", ["loan_id"]),
        ("ix_portfolio_risk_snapshots_borrower_id", ["borrower_id"]),
        ("ix_portfolio_risk_snapshots_employer_group_id", ["employer_group_id"]),
        ("ix_portfolio_risk_snapshots_product_id", ["product_id"]),
        ("ix_portfolio_risk_snapshots_snapshot_date", ["snapshot_date"]),
        ("ix_portfolio_risk_snapshots_origination_month", ["origination_month"]),
        ("ix_portfolio_risk_snapshots_days_past_due", ["days_past_due"]),
        ("ix_portfolio_risk_snapshots_delinquency_bucket", ["delinquency_bucket"]),
        ("ix_portfolio_risk_snapshots_loan_status", ["loan_status"]),
        ("ix_portfolio_risk_snapshots_origination_channel", ["origination_channel"]),
        ("ix_portfolio_risk_snapshots_collection_channel", ["collection_channel"]),
        ("ix_portfolio_risk_snapshots_is_top_up", ["is_top_up"]),
        ("ix_portfolio_risk_snapshots_first_payment_default", ["first_payment_default"]),
        ("ix_portfolio_risk_snapshots_is_written_off", ["is_written_off"]),
        ("ix_portfolio_risk_snapshots_cdas_collection_enabled", ["cdas_collection_enabled"]),
    ):
        op.create_index(name, "portfolio_risk_snapshots", cols)

    op.create_table(
        "portfolio_risk_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_scope_key", sa.String(length=40), server_default="ALL", nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("loan_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active_exposure", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("par_30_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "snapshot_date", "branch_scope_key", name="uq_portfolio_risk_run_company_date_scope"),
        sa.UniqueConstraint("run_reference"),
    )
    op.create_index("ix_portfolio_risk_runs_company_id", "portfolio_risk_runs", ["company_id"])
    op.create_index("ix_portfolio_risk_runs_branch_id", "portfolio_risk_runs", ["branch_id"])
    op.create_index("ix_portfolio_risk_runs_snapshot_date", "portfolio_risk_runs", ["snapshot_date"])
    op.create_index("ix_portfolio_risk_runs_run_reference", "portfolio_risk_runs", ["run_reference"])


def downgrade() -> None:
    op.drop_table("portfolio_risk_runs")
    op.drop_table("portfolio_risk_snapshots")
