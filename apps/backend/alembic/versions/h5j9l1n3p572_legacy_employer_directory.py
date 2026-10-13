"""Company-scoped employer directory for legacy bank deductions.

Revision ID: h5j9l1n3p572
Revises: h5j9l1n3p571
"""
from alembic import op
import sqlalchemy as sa

revision = "h5j9l1n3p572"
down_revision = "h5j9l1n3p571"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legacy_employers",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("loan_companies.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.UniqueConstraint("company_id", "normalized_name", name="uq_legacy_employers_company_normalized"),
    )
    op.create_index("ix_legacy_employers_company_id", "legacy_employers", ["company_id"])


def downgrade():
    op.drop_index("ix_legacy_employers_company_id", table_name="legacy_employers")
    op.drop_table("legacy_employers")
