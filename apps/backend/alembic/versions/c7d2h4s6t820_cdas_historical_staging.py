"""Add isolated historical CDAS import staging tables.

Revision ID: c7d2h4s6t820
Revises: w1p2a3d4s516
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c7d2h4s6t820"
down_revision = "w1p2a3d4s516"
branch_labels = None
depends_on = None


def _base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
    ]


def upgrade():
    op.create_table(
        "cdas_historical_import_batches",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("imported_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("company_id", "branch_id", "source_sha256", name="uq_cdas_history_batch_source"),
    )
    op.create_index("uq_cdas_history_batch_unbranched_source", "cdas_historical_import_batches", ["company_id", "source_sha256"], unique=True, postgresql_where=sa.text("branch_id IS NULL"))
    for col in ("company_id", "branch_id", "source_sha256", "status"):
        op.create_index(f"ix_cdas_historical_import_batches_{col}", "cdas_historical_import_batches", [col])
    op.create_table(
        "cdas_historical_import_rows",
        *_base_columns(),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cdas_historical_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("employee_no", sa.String(100), nullable=False),
        sa.Column("employee_name", sa.String(255), nullable=True),
        sa.Column("policy_reference", sa.String(200), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(15,2), nullable=False),
        sa.Column("principal_amount", sa.Numeric(15,2), nullable=False),
        sa.Column("total_installments", sa.Integer(), nullable=False),
        sa.Column("starting_month", sa.String(40), nullable=True),
        sa.Column("ending_month", sa.String(40), nullable=True),
        sa.Column("reconciliation_status", sa.String(30), nullable=False),
        sa.Column("matched_mandate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cdas_deduction_mandates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_record", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("batch_id", "line_number", name="uq_cdas_history_batch_line"),
    )
    for col in ("batch_id", "company_id", "branch_id", "employee_no", "policy_reference", "reconciliation_status"):
        op.create_index(f"ix_cdas_historical_import_rows_{col}", "cdas_historical_import_rows", [col])


def downgrade():
    op.drop_table("cdas_historical_import_rows")
    op.drop_table("cdas_historical_import_batches")
