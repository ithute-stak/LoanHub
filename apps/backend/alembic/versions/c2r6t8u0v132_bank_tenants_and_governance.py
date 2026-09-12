"""bank tenants and institution governance

Revision ID: c2r6t8u0v132
Revises: b1q5s7t9u021
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2r6t8u0v132"
down_revision: Union[str, Sequence[str], None] = "b1q5s7t9u021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INSTITUTION_TYPES = (
    "LOAN_COMPANY",
    "COMMERCIAL_BANK",
    "MICROFINANCE_INSTITUTION",
    "FINANCIAL_COOPERATIVE",
    "DEVELOPMENT_FINANCE_INSTITUTION",
    "GOVERNMENT_LENDING_PROGRAM",
)

REGULATED_ROLES = (
    "CREDIT_ANALYST",
    "AML_CFT_OFFICER",
    "TREASURY_OFFICER",
    "DATA_PROTECTION_OFFICER",
    "REGULATORY_REPORTING_OFFICER",
    "OPERATIONS_OFFICER",
    "INFORMATION_SECURITY_OFFICER",
)


def upgrade() -> None:
    institution_type = postgresql.ENUM(
        *INSTITUTION_TYPES,
        name="institutiontype",
        create_type=False,
    )
    institution_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "loan_companies",
        sa.Column(
            "institution_type",
            institution_type,
            nullable=False,
            server_default="LOAN_COMPANY",
        ),
    )
    op.create_index(
        "ix_loan_companies_institution_type",
        "loan_companies",
        ["institution_type"],
        unique=False,
    )

    for role in REGULATED_ROLES:
        # Values are controlled constants declared above, not user input.
        op.execute(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{role}'")

    op.create_table(
        "institution_governance_profiles",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("regulator_name", sa.String(length=200), nullable=True),
        sa.Column("regulatory_license_category", sa.String(length=160), nullable=True),
        sa.Column("license_expiry_date", sa.Date(), nullable=True),
        sa.Column("bank_code", sa.String(length=40), nullable=True),
        sa.Column("swift_bic", sa.String(length=20), nullable=True),
        sa.Column("aml_cft_officer_name", sa.String(length=200), nullable=True),
        sa.Column("aml_cft_officer_email", sa.String(length=200), nullable=True),
        sa.Column("data_protection_officer_name", sa.String(length=200), nullable=True),
        sa.Column("data_protection_officer_email", sa.String(length=200), nullable=True),
        sa.Column("regulatory_reporting_contact_email", sa.String(length=200), nullable=True),
        sa.Column("complaints_contact", sa.String(length=200), nullable=True),
        sa.Column("privacy_notice_url", sa.String(length=500), nullable=True),
        sa.Column("data_retention_months", sa.Integer(), server_default="60", nullable=False),
        sa.Column("consent_management_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("data_export_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ai_decisioning_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ai_human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("ai_explainability_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("ai_bias_monitoring_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("govstack_interoperability_status", sa.String(length=40), server_default="not_started", nullable=False),
        sa.Column("dpg_readiness_status", sa.String(length=40), server_default="not_started", nullable=False),
        sa.Column("open_api_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("low_bandwidth_supported", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("accessibility_reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("english_sesotho_supported", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("business_continuity_tested", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("incident_response_tested", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("interoperability_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(
        "ix_institution_governance_profiles_company_id",
        "institution_governance_profiles",
        ["company_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_institution_governance_profiles_company_id",
        table_name="institution_governance_profiles",
    )
    op.drop_table("institution_governance_profiles")
    op.drop_index(
        "ix_loan_companies_institution_type",
        table_name="loan_companies",
    )
    op.drop_column("loan_companies", "institution_type")
    postgresql.ENUM(name="institutiontype").drop(
        op.get_bind(),
        checkfirst=True,
    )
    # PostgreSQL enum values cannot be removed safely in-place. The additional
    # user roles remain available after downgrade to preserve existing records.
