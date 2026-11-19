"""Persist reservation for individually requested CDAS affordability assessments.

Revision ID: c1d3a5f7b061
Revises: b7c9d1e3f055
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1d3a5f7b061"
down_revision = "b7c9d1e3f055"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cdas_affordability_attempts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), server_default="reserved", nullable=False),
        sa.Column("assessment_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_cdas_aff_attempt_company_key"),
        sa.CheckConstraint("state IN ('reserved','unknown','identity_review','completed')", name="ck_cdas_aff_attempt_state"),
    )
    op.create_index("ix_cdas_affordability_attempts_company_id", "cdas_affordability_attempts", ["company_id"])
    op.create_index("ix_cdas_aff_attempt_company_borrower", "cdas_affordability_attempts", ["company_id", "borrower_id"])
    op.create_index(
        "uq_cdas_aff_attempt_unresolved_fingerprint",
        "cdas_affordability_attempts",
        ["company_id", "request_fingerprint"],
        unique=True,
        postgresql_where=sa.text("state IN ('reserved','unknown')"),
    )


def downgrade():
    op.drop_index("uq_cdas_aff_attempt_unresolved_fingerprint", table_name="cdas_affordability_attempts")
    op.drop_index("ix_cdas_aff_attempt_company_borrower", table_name="cdas_affordability_attempts")
    op.drop_index("ix_cdas_affordability_attempts_company_id", table_name="cdas_affordability_attempts")
    op.drop_table("cdas_affordability_attempts")
