"""Add company default loan contract template setting.

Revision ID: k1a5c7d9f011
Revises: j0z4b6c8e910
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "k1a5c7d9f011"
down_revision = "j0z4b6c8e910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_loan_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "default_contract_template_style",
            sa.String(length=50),
            server_default="loanhub_standard",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["loan_companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            name="uq_company_loan_settings_company_id",
        ),
    )
    op.create_index(
        "ix_company_loan_settings_company_id",
        "company_loan_settings",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_loan_settings_company_id",
        table_name="company_loan_settings",
    )
    op.drop_table("company_loan_settings")
