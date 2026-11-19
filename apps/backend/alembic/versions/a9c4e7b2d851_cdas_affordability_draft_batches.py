"""Persist execution-disabled CDAS affordability batch drafts.

Revision ID: a9c4e7b2d851
Revises: z9n3p5q7r800
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a9c4e7b2d851"
down_revision = "z9n3p5q7r800"
branch_labels = None
depends_on = None


def _base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
    ]


def upgrade():
    op.create_table(
        "cdas_affordability_batches",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("consent_evidence_reference", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("finished_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_cdas_affordability_batch_idempotency"),
        sa.CheckConstraint("total_count BETWEEN 1 AND 20", name="ck_cdas_affordability_batch_count"),
        sa.CheckConstraint("finished_count >= 0 AND finished_count <= total_count", name="ck_cdas_affordability_batch_finished"),
        sa.CheckConstraint("execution_enabled = false", name="ck_cdas_affordability_batch_execution_disabled"),
        sa.CheckConstraint("status IN ('draft', 'cancelled')", name="ck_cdas_affordability_batch_status"),
    )
    op.create_index("ix_cdas_affordability_batches_company_id", "cdas_affordability_batches", ["company_id"])
    op.create_index("ix_cdas_affordability_batches_status", "cdas_affordability_batches", ["status"])

    op.create_table(
        "cdas_affordability_batch_items",
        *_base_columns(),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_number", sa.String(100), nullable=False),
        sa.Column("proposed_monthly_installment", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("assessment_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["batch_id"], ["cdas_affordability_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_id", "borrower_id", name="uq_cdas_affordability_batch_borrower"),
        sa.UniqueConstraint("batch_id", "employee_number", name="uq_cdas_affordability_batch_employee"),
        sa.CheckConstraint("proposed_monthly_installment > 0", name="ck_cdas_affordability_batch_item_installment"),
        sa.CheckConstraint("attempt_count = 0", name="ck_cdas_affordability_batch_item_no_execution"),
        sa.CheckConstraint("status = 'pending'", name="ck_cdas_affordability_batch_item_pending"),
    )
    op.create_index("ix_cdas_affordability_batch_items_batch_id", "cdas_affordability_batch_items", ["batch_id"])
    op.create_index("ix_cdas_affordability_batch_items_company_id", "cdas_affordability_batch_items", ["company_id"])


def downgrade():
    op.drop_index("ix_cdas_affordability_batch_items_company_id", table_name="cdas_affordability_batch_items")
    op.drop_index("ix_cdas_affordability_batch_items_batch_id", table_name="cdas_affordability_batch_items")
    op.drop_table("cdas_affordability_batch_items")
    op.drop_index("ix_cdas_affordability_batches_status", table_name="cdas_affordability_batches")
    op.drop_index("ix_cdas_affordability_batches_company_id", table_name="cdas_affordability_batches")
    op.drop_table("cdas_affordability_batches")
