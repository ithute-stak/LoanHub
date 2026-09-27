"""add proper reconciliation engine

Revision ID: n8u9w0y1z201
Revises: m7t8v9x0y101
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "n8u9w0y1z201"
down_revision = "m7t8v9x0y101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_reference", sa.String(length=90), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference", sa.String(length=180), nullable=True),
        sa.Column("account_reference", sa.String(length=180), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="LSL", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("imported_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("exception_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_line_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("missing_source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("matched_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("shortage_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("excess_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("unmatched_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("close_note", sa.Text(), nullable=True),
        sa.Column("methodology_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("period_end >= period_start", name="ck_reconciliation_batch_period"),
        sa.CheckConstraint("source_type IN ('bank_statement','payment_provider','employer_payroll','cdas_remittance','manual_import')", name="ck_reconciliation_batch_source_type"),
        sa.CheckConstraint("status IN ('draft','imported','in_review','reconciled','exception','closed')", name="ck_reconciliation_batch_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "batch_reference", name="uq_reconciliation_batch_company_reference"),
    )
    for name, columns in (
        ("ix_reconciliation_batches_company_id", ["company_id"]),
        ("ix_reconciliation_batches_branch_id", ["branch_id"]),
        ("ix_reconciliation_batches_batch_reference", ["batch_reference"]),
        ("ix_reconciliation_batches_source_type", ["source_type"]),
        ("ix_reconciliation_batches_source_reference", ["source_reference"]),
        ("ix_reconciliation_batches_account_reference", ["account_reference"]),
        ("ix_reconciliation_batches_period_start", ["period_start"]),
        ("ix_reconciliation_batches_period_end", ["period_end"]),
        ("ix_reconciliation_batches_status", ["status"]),
    ):
        op.create_index(name, "reconciliation_batches", columns)

    op.create_table(
        "reconciliation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(length=30), server_default="external", nullable=False),
        sa.Column("source_line_key", sa.String(length=180), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=220), nullable=True),
        sa.Column("description", sa.String(length=700), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="LSL", nullable=False),
        sa.Column("direction", sa.String(length=12), server_default="credit", nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="unmatched", nullable=False),
        sa.Column("match_method", sa.String(length=60), nullable=True),
        sa.Column("match_confidence", sa.Numeric(6, 3), nullable=True),
        sa.Column("matched_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("folio_number", sa.String(length=40), nullable=True),
        sa.Column("expected_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("variance_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("exception_code", sa.String(length=80), nullable=True),
        sa.Column("exception_reason", sa.Text(), nullable=True),
        sa.Column("candidate_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_manual_match", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("matched_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("payment_adjustment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("source_kind IN ('external','system_expected')", name="ck_reconciliation_line_source_kind"),
        sa.CheckConstraint("direction IN ('credit','debit')", name="ck_reconciliation_line_direction"),
        sa.CheckConstraint("status IN ('unmatched','matched','duplicate','shortage','excess','missing_source','ignored','adjustment_required')", name="ck_reconciliation_line_status"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["reconciliation_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_payment_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_adjustment_id"], ["payment_adjustments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "source_line_key", name="uq_reconciliation_line_batch_source_key"),
    )
    for name, columns in (
        ("ix_reconciliation_lines_company_id", ["company_id"]),
        ("ix_reconciliation_lines_batch_id", ["batch_id"]),
        ("ix_reconciliation_lines_source_kind", ["source_kind"]),
        ("ix_reconciliation_lines_transaction_date", ["transaction_date"]),
        ("ix_reconciliation_lines_reference", ["reference"]),
        ("ix_reconciliation_lines_direction", ["direction"]),
        ("ix_reconciliation_lines_source_fingerprint", ["source_fingerprint"]),
        ("ix_reconciliation_lines_status", ["status"]),
        ("ix_reconciliation_lines_match_method", ["match_method"]),
        ("ix_reconciliation_lines_matched_payment_id", ["matched_payment_id"]),
        ("ix_reconciliation_lines_matched_loan_id", ["matched_loan_id"]),
        ("ix_reconciliation_lines_matched_borrower_id", ["matched_borrower_id"]),
        ("ix_reconciliation_lines_folio_number", ["folio_number"]),
        ("ix_reconciliation_lines_exception_code", ["exception_code"]),
        ("ix_reconciliation_lines_payment_adjustment_id", ["payment_adjustment_id"]),
    ):
        op.create_index(name, "reconciliation_lines", columns)

    op.create_table(
        "reconciliation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["reconciliation_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["line_id"], ["reconciliation_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_events_company_id", "reconciliation_events", ["company_id"])
    op.create_index("ix_reconciliation_events_batch_id", "reconciliation_events", ["batch_id"])
    op.create_index("ix_reconciliation_events_line_id", "reconciliation_events", ["line_id"])
    op.create_index("ix_reconciliation_events_event_type", "reconciliation_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("reconciliation_events")
    op.drop_table("reconciliation_lines")
    op.drop_table("reconciliation_batches")
