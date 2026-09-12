"""company public website builder

Revision ID: b1q5s7u9v021
Revises: a0p4r6s8t910
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1q5s7u9v021"
down_revision: Union[str, Sequence[str], None] = "a0p4r6s8t910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_website_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_code", sa.String(length=90), nullable=False),
        sa.Column("template_key", sa.String(length=40), server_default="trust_community", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("headline", sa.String(length=180), nullable=False),
        sa.Column("subheadline", sa.Text(), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=12), server_default="#0F4C81", nullable=False),
        sa.Column("accent_color", sa.String(length=12), server_default="#16A34A", nullable=False),
        sa.Column("hero_badge", sa.String(length=120), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("show_loan_products", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("show_account_cta", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("custom_sections", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_company_website_profiles_company_id"),
        sa.UniqueConstraint("public_code", name="uq_company_website_profiles_public_code"),
    )
    op.create_index("ix_company_website_profiles_company_id", "company_website_profiles", ["company_id"], unique=True)
    op.create_index("ix_company_website_profiles_public_code", "company_website_profiles", ["public_code"], unique=True)
    op.create_index("ix_company_website_profiles_is_published", "company_website_profiles", ["is_published"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_company_website_profiles_is_published", table_name="company_website_profiles")
    op.drop_index("ix_company_website_profiles_public_code", table_name="company_website_profiles")
    op.drop_index("ix_company_website_profiles_company_id", table_name="company_website_profiles")
    op.drop_table("company_website_profiles")
