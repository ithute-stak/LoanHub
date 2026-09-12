"""Enterprise credit origination, KYC, affordability and contracts.

Revision ID: h7c2a9d4e810
Revises: g4d8e1f2a760
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h7c2a9d4e810"
down_revision = "g4d8e1f2a760"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "origination_policies",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_concurrent_active_loans", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_active_loans", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_open_applications", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allow_top_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cooling_off_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_age", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("max_age", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("min_verified_net_income", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("max_dti_percent", sa.Numeric(8, 3), nullable=False, server_default="40"),
        sa.Column("max_installment_income_percent", sa.Numeric(8, 3), nullable=False, server_default="35"),
        sa.Column("disposable_income_usage_percent", sa.Numeric(8, 3), nullable=False, server_default="70"),
        sa.Column("min_disposable_after_installment", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("living_expense_buffer", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("dependant_allowance", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("min_employment_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_payslips", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("required_bank_statement_months", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("require_kyc_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_signed_contract", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_blacklisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manager_override_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_origination_policy_company"),
    )
    op.create_index("ix_origination_policies_company_id", "origination_policies", ["company_id"])

    op.create_table(
        "borrower_kyc_profiles",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="not_started"),
        sa.Column("identity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("address_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sanctions_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("politically_exposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adverse_media_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fraud_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_of_funds", sa.String(length=200), nullable=True),
        sa.Column("residence_status", sa.String(length=60), nullable=True),
        sa.Column("years_at_address", sa.Numeric(6, 2), nullable=True),
        sa.Column("dependants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_of_kin", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("emergency_contact", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("document_file_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "borrower_id", name="uq_kyc_company_borrower"),
    )
    op.create_index("ix_borrower_kyc_profiles_company_id", "borrower_kyc_profiles", ["company_id"])
    op.create_index("ix_borrower_kyc_profiles_borrower_id", "borrower_kyc_profiles", ["borrower_id"])
    op.create_index("ix_borrower_kyc_profiles_status", "borrower_kyc_profiles", ["status"])

    op.create_table(
        "borrower_employment_profiles",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employment_status", sa.String(length=40), nullable=False, server_default="employed"),
        sa.Column("employer_name", sa.String(length=200), nullable=True),
        sa.Column("employer_registration", sa.String(length=100), nullable=True),
        sa.Column("employer_phone", sa.String(length=40), nullable=True),
        sa.Column("employer_address", sa.Text(), nullable=True),
        sa.Column("employee_number", sa.String(length=100), nullable=True),
        sa.Column("job_title", sa.String(length=150), nullable=True),
        sa.Column("employment_start_date", sa.Date(), nullable=True),
        sa.Column("contract_type", sa.String(length=60), nullable=True),
        sa.Column("contract_expiry_date", sa.Date(), nullable=True),
        sa.Column("salary_frequency", sa.String(length=30), nullable=False, server_default="monthly"),
        sa.Column("gross_salary", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("net_salary", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("verified_net_income", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("salary_day", sa.Integer(), nullable=True),
        sa.Column("verification_method", sa.String(length=100), nullable=True),
        sa.Column("verification_status", sa.String(length=40), nullable=False, server_default="unverified"),
        sa.Column("payslip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bank_statement_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "borrower_id", name="uq_employment_company_borrower"),
    )
    op.create_index("ix_borrower_employment_profiles_company_id", "borrower_employment_profiles", ["company_id"])
    op.create_index("ix_borrower_employment_profiles_borrower_id", "borrower_employment_profiles", ["borrower_id"])

    for table_name, columns in [
        ("borrower_income_sources", [
            sa.Column("source_type", sa.String(length=60), nullable=False),
            sa.Column("description", sa.String(length=240), nullable=True),
            sa.Column("declared_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("verified_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("frequency", sa.String(length=30), nullable=False, server_default="monthly"),
            sa.Column("verification_method", sa.String(length=100), nullable=True),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        ]),
        ("borrower_expenses", [
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=240), nullable=True),
            sa.Column("monthly_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("verification_notes", sa.Text(), nullable=True),
        ]),
        ("borrower_debt_obligations", [
            sa.Column("creditor", sa.String(length=200), nullable=False),
            sa.Column("account_reference", sa.String(length=140), nullable=True),
            sa.Column("debt_type", sa.String(length=80), nullable=False, server_default="other"),
            sa.Column("original_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("current_balance", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("monthly_installment", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("settlement_amount", sa.Numeric(15, 2), nullable=True),
            sa.Column("remaining_term_months", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=60), nullable=False, server_default="declared"),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        ]),
    ]:
        op.create_table(
            table_name,
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
            *columns,
            *audit_columns(),
            sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table_name}_company_id", table_name, ["company_id"])
        op.create_index(f"ix_{table_name}_borrower_id", table_name, ["borrower_id"])

    op.create_table(
        "borrower_bank_accounts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_holder", sa.String(length=200), nullable=False),
        sa.Column("bank_name", sa.String(length=160), nullable=False),
        sa.Column("branch_name", sa.String(length=160), nullable=True),
        sa.Column("branch_code", sa.String(length=40), nullable=True),
        sa.Column("account_type", sa.String(length=40), nullable=False, server_default="savings"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("account_number_encrypted", sa.Text(), nullable=False),
        sa.Column("account_number_last4", sa.String(length=4), nullable=False),
        sa.Column("salary_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(length=40), nullable=False, server_default="unverified"),
        sa.Column("verification_reference", sa.String(length=180), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("tokenized_card_provider", sa.String(length=80), nullable=True),
        sa.Column("tokenized_card_reference_encrypted", sa.Text(), nullable=True),
        sa.Column("masked_card_number", sa.String(length=30), nullable=True),
        sa.Column("card_brand", sa.String(length=30), nullable=True),
        sa.Column("card_expiry_month", sa.Integer(), nullable=True),
        sa.Column("card_expiry_year", sa.Integer(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "borrower_id", name="uq_bank_company_borrower"),
    )
    op.create_index("ix_borrower_bank_accounts_company_id", "borrower_bank_accounts", ["company_id"])
    op.create_index("ix_borrower_bank_accounts_borrower_id", "borrower_bank_accounts", ["borrower_id"])

    op.add_column("direct_loan_applications", sa.Column("preferred_payment_day", sa.Integer(), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("first_payment_date", sa.Date(), nullable=True))
    op.add_column("direct_loan_applications", sa.Column("application_step", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("direct_loan_applications", sa.Column("kyc_profile_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_direct_application_kyc", "direct_loan_applications", "borrower_kyc_profiles", ["kyc_profile_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "affordability_assessments",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("assessment_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("verified_income", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("household_expenses", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("existing_debt_installments", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("configured_buffer", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("dependant_allowance_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("disposable_income", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("dti_percent", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("disposable_income_limit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("dti_limit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("installment_income_limit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("maximum_affordable_installment", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("proposed_installment", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("affordability_headroom", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("calculated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_decision", sa.String(length=50), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("overridden_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("overridden_at", sa.DateTime(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["direct_loan_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["origination_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["calculated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["overridden_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_affordability_assessments_company_id", "affordability_assessments", ["company_id"])
    op.create_index("ix_affordability_assessments_borrower_id", "affordability_assessments", ["borrower_id"])
    op.create_index("ix_affordability_assessments_application_id", "affordability_assessments", ["application_id"])
    op.create_index("ix_affordability_assessments_decision", "affordability_assessments", ["decision"])
    op.add_column("direct_loan_applications", sa.Column("affordability_assessment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_direct_application_affordability", "direct_loan_applications", "affordability_assessments", ["affordability_assessment_id"], ["id"], ondelete="SET NULL", use_alter=True)

    op.add_column("client_company_loan", sa.Column("preferred_payment_day", sa.Integer(), nullable=True))

    op.create_table(
        "loan_contracts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_number", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("terms_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("contract_hash", sa.String(length=64), nullable=False),
        sa.Column("pdf_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_signature_name", sa.String(length=200), nullable=True),
        sa.Column("borrower_signed_at", sa.DateTime(), nullable=True),
        sa.Column("borrower_signature_method", sa.String(length=40), nullable=True),
        sa.Column("company_signer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_signed_at", sa.DateTime(), nullable=True),
        sa.Column("company_signature_method", sa.String(length=40), nullable=True),
        sa.Column("witness_name", sa.String(length=200), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["direct_loan_applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pdf_file_id"], ["managed_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_signer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id", name="uq_loan_contract_loan"),
        sa.UniqueConstraint("contract_number", name="uq_loan_contract_number"),
    )
    op.create_index("ix_loan_contracts_company_id", "loan_contracts", ["company_id"])
    op.create_index("ix_loan_contracts_borrower_id", "loan_contracts", ["borrower_id"])
    op.create_index("ix_loan_contracts_application_id", "loan_contracts", ["application_id"])
    op.create_index("ix_loan_contracts_loan_id", "loan_contracts", ["loan_id"])
    op.create_index("ix_loan_contracts_contract_number", "loan_contracts", ["contract_number"])
    op.create_index("ix_loan_contracts_status", "loan_contracts", ["status"])

    op.create_table(
        "origination_integration_configurations",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=30), nullable=False, server_default="sandbox"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("last_test_status", sa.String(length=40), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "provider", name="uq_origination_integration_company_provider"),
    )
    op.create_index("ix_origination_integration_configurations_company_id", "origination_integration_configurations", ["company_id"])
    op.create_index("ix_origination_integration_configurations_provider", "origination_integration_configurations", ["provider"])


def downgrade() -> None:
    op.drop_table("origination_integration_configurations")
    op.drop_table("loan_contracts")
    op.drop_column("client_company_loan", "preferred_payment_day")
    op.drop_constraint("fk_direct_application_affordability", "direct_loan_applications", type_="foreignkey")
    op.drop_column("direct_loan_applications", "affordability_assessment_id")
    op.drop_table("affordability_assessments")
    op.drop_constraint("fk_direct_application_kyc", "direct_loan_applications", type_="foreignkey")
    op.drop_column("direct_loan_applications", "kyc_profile_id")
    op.drop_column("direct_loan_applications", "application_step")
    op.drop_column("direct_loan_applications", "first_payment_date")
    op.drop_column("direct_loan_applications", "preferred_payment_day")
    op.drop_table("borrower_bank_accounts")
    op.drop_table("borrower_debt_obligations")
    op.drop_table("borrower_expenses")
    op.drop_table("borrower_income_sources")
    op.drop_table("borrower_employment_profiles")
    op.drop_table("borrower_kyc_profiles")
    op.drop_table("origination_policies")
