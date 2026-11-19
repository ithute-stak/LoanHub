"""Create purpose-specific CDAS affordability consent review evidence.

Revision ID: e3f5a7c9d063
Revises: d2e4f6a8b062

Records begin pending: no verification or CDAS execution is enabled here.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e3f5a7c9d063"
down_revision = "d2e4f6a8b062"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cdas_affordability_consent_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_number", sa.String(100), nullable=False),
        sa.Column("reference", sa.String(200), nullable=False),
        sa.Column("purpose", sa.String(100), server_default="cdas_government_employee_affordability", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=True),
        sa.Column("borrower_authorization_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','revoked')",
            name="ck_cdas_aff_consent_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["borrower_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_cdas_aff_consent_company_borrower",
        "cdas_affordability_consent_evidence", ["company_id", "borrower_id"],
    )
    op.create_index(
        "ix_cdas_aff_consent_company_reference",
        "cdas_affordability_consent_evidence", ["company_id", "reference"], unique=True,
    )


def downgrade():
    op.drop_index("ix_cdas_aff_consent_company_reference", table_name="cdas_affordability_consent_evidence")
    op.drop_index("ix_cdas_aff_consent_company_borrower", table_name="cdas_affordability_consent_evidence")
    op.drop_table("cdas_affordability_consent_evidence")
