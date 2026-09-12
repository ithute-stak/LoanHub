"""Cashless payments, service fees, platform charging and role switching.

Revision ID: c4f9e2d7a110
Revises: b8d5e21f9a30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4f9e2d7a110"
down_revision = "b8d5e21f9a30"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade():
    # PostgreSQL enum labels are append-only in this release. Downgrade keeps
    # labels because safely removing them requires recreating the enum types.
    for role in (
        "platform_admin",
        "platform_finance",
        "platform_support",
        "platform_auditor",
        "platform_operations",
        "platform_compliance",
    ):
        op.execute(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{role}'")
    op.execute("ALTER TYPE paymentprovider ADD VALUE IF NOT EXISTS 'eft'")
    for purpose in (
        "borrow_request_fee",
        "platform_transaction_charge",
        "platform_claim_settlement",
        "direct_debit",
    ):
        op.execute(f"ALTER TYPE paymentpurpose ADD VALUE IF NOT EXISTS '{purpose}'")

    # One account may hold multiple roles in the same tenant. Exactly one can be
    # marked primary; role selection is sent in X-Active-Role.
    op.add_column(
        "company_staff",
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id, company_id ORDER BY created_at ASC, id ASC
            ) AS rn
            FROM company_staff
        )
        UPDATE company_staff cs
        SET is_primary = true
        FROM ranked r
        WHERE cs.id = r.id AND r.rn = 1
        """
    )
    op.drop_constraint("uq_company_staff_user_company", "company_staff", type_="unique")
    op.create_unique_constraint(
        "uq_company_staff_user_company_role",
        "company_staff",
        ["user_id", "company_id", "role"],
    )

    # M-Pesa credentials can belong to either a tenant company or the platform
    # receipt account used for borrower service fees and platform claims.
    op.add_column("mpesa_configurations", sa.Column("scope_key", sa.String(length=80), nullable=True))
    op.add_column(
        "mpesa_configurations",
        sa.Column("scope_type", sa.String(length=20), server_default="company", nullable=False),
    )
    op.execute("UPDATE mpesa_configurations SET scope_key = 'company:' || company_id::text")
    op.alter_column("mpesa_configurations", "scope_key", nullable=False)
    op.drop_constraint("uq_mpesa_configuration_company", "mpesa_configurations", type_="unique")
    op.alter_column("mpesa_configurations", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_unique_constraint("uq_mpesa_configuration_scope", "mpesa_configurations", ["scope_key"])
    op.create_index("ix_mpesa_configurations_scope_key", "mpesa_configurations", ["scope_key"])
    op.create_index("ix_mpesa_configurations_scope_type", "mpesa_configurations", ["scope_type"])

    # Link payments to walk-in applications and add the online request fee
    # snapshot. The snapshot protects historical requests from later fee edits.
    op.add_column(
        "payment_transactions",
        sa.Column("direct_application_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_transactions_direct_application_id",
        "payment_transactions",
        "direct_loan_applications",
        ["direct_application_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_payment_transactions_direct_application_id",
        "payment_transactions",
        ["direct_application_id"],
    )

    op.add_column(
        "loan_requests",
        sa.Column("origination_channel", sa.String(length=30), server_default="online", nullable=False),
    )
    op.add_column(
        "loan_requests",
        sa.Column("captured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "loan_requests",
        sa.Column("service_fee_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "loan_requests",
        sa.Column("service_fee_currency", sa.String(length=3), server_default="LSL", nullable=False),
    )
    op.add_column(
        "loan_requests",
        sa.Column("service_fee_status", sa.String(length=30), server_default="not_required", nullable=False),
    )
    op.add_column(
        "loan_requests",
        sa.Column("service_fee_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_loan_requests_captured_by_user_id",
        "loan_requests",
        "users",
        ["captured_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_loan_requests_service_fee_payment_id",
        "loan_requests",
        "payment_transactions",
        ["service_fee_payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_loan_requests_service_fee_payment_id",
        "loan_requests",
        ["service_fee_payment_id"],
    )
    op.create_index("ix_loan_requests_captured_by_user_id", "loan_requests", ["captured_by_user_id"])
    op.create_index("ix_loan_requests_service_fee_status", "loan_requests", ["service_fee_status"])

    op.create_table(
        "borrower_fee_configurations",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("fee_type", sa.String(length=20), nullable=False),
        sa.Column("flat_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(10, 6), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("maximum_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("required_before_submission", sa.Boolean(), nullable=False),
        sa.Column("refundable", sa.Boolean(), nullable=False),
        sa.Column("allowed_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_borrower_fee_configurations_company_id", "borrower_fee_configurations", ["company_id"])
    op.create_index("ix_borrower_fee_configurations_is_active", "borrower_fee_configurations", ["is_active"])

    op.create_table(
        "ecocash_configurations",
        *audit_columns(),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("msisdn_country_prefix", sa.String(length=8), nullable=False),
        sa.Column("merchant_code", sa.String(length=80), nullable=False),
        sa.Column("merchant_number", sa.String(length=40), nullable=False),
        sa.Column("merchant_pin_encrypted", sa.Text(), nullable=False),
        sa.Column("username_encrypted", sa.Text(), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("terminal_id", sa.String(length=80), nullable=False),
        sa.Column("merchant_name", sa.String(length=180), nullable=False),
        sa.Column("super_merchant_name", sa.String(length=180), nullable=True),
        sa.Column("location", sa.String(length=180), nullable=True),
        sa.Column("callback_base_url", sa.String(length=500), nullable=True),
        sa.Column("callback_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled_products", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("production_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_connection_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_connection_test_status", sa.String(length=30), nullable=True),
        sa.Column("last_connection_test_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("scope_key", name="uq_ecocash_configuration_scope"),
    )
    for column in ["scope_key", "scope_type", "company_id", "is_active"]:
        op.create_index(f"ix_ecocash_configurations_{column}", "ecocash_configurations", [column])

    op.create_table(
        "ecocash_provider_transactions",
        *audit_columns(),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("client_correlator", sa.String(length=100), nullable=False),
        sa.Column("reference_code", sa.String(length=120), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=120), nullable=True),
        sa.Column("original_provider_reference", sa.String(length=120), nullable=True),
        sa.Column("provider_status", sa.String(length=40), nullable=False),
        sa.Column("response_code", sa.String(length=30), nullable=True),
        sa.Column("response_message", sa.Text(), nullable=True),
        sa.Column("sanitized_request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("callback_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lookup_count", sa.Integer(), nullable=False),
        sa.Column("last_lookup_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configuration_id"], ["ecocash_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payment_id", name="uq_ecocash_provider_payment"),
        sa.UniqueConstraint("client_correlator", name="uq_ecocash_client_correlator"),
    )
    for column in [
        "payment_id", "configuration_id", "company_id", "borrower_id", "operation_type",
        "client_correlator", "reference_code", "provider_transaction_id",
        "original_provider_reference", "provider_status",
    ]:
        op.create_index(f"ix_ecocash_provider_transactions_{column}", "ecocash_provider_transactions", [column])

    op.create_table(
        "ecocash_callback_events",
        *audit_columns(),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_status", sa.String(length=30), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["configuration_id"], ["ecocash_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_transaction_id"], ["ecocash_provider_transactions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payload_hash", name="uq_ecocash_callback_hash"),
    )
    for column in ["configuration_id", "provider_transaction_id", "payload_hash", "processing_status"]:
        op.create_index(f"ix_ecocash_callback_events_{column}", "ecocash_callback_events", [column])

    op.create_table(
        "eft_configurations",
        *audit_columns(),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("bank_name", sa.String(length=180), nullable=False),
        sa.Column("account_name", sa.String(length=180), nullable=False),
        sa.Column("account_number_encrypted", sa.Text(), nullable=False),
        sa.Column("branch_code", sa.String(length=40), nullable=True),
        sa.Column("swift_code", sa.String(length=40), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("integration_mode", sa.String(length=30), nullable=False),
        sa.Column("api_base_url", sa.String(length=500), nullable=True),
        sa.Column("client_id_encrypted", sa.Text(), nullable=True),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("signing_key_encrypted", sa.Text(), nullable=True),
        sa.Column("callback_base_url", sa.String(length=500), nullable=True),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("maker_checker_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("production_enabled", sa.Boolean(), nullable=False),
        sa.Column("reconciliation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_connection_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_connection_test_status", sa.String(length=30), nullable=True),
        sa.Column("last_connection_test_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("scope_key", name="uq_eft_configuration_scope"),
    )
    for column in ["scope_key", "scope_type", "company_id", "is_active"]:
        op.create_index(f"ix_eft_configurations_{column}", "eft_configurations", [column])

    op.create_table(
        "eft_provider_transactions",
        *audit_columns(),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bank_reference", sa.String(length=160), nullable=True),
        sa.Column("instruction_reference", sa.String(length=100), nullable=False),
        sa.Column("provider_status", sa.String(length=40), nullable=False),
        sa.Column("payer_account_masked", sa.String(length=60), nullable=True),
        sa.Column("beneficiary_account_masked", sa.String(length=60), nullable=True),
        sa.Column("proof_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("initiated_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reconciled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configuration_id"], ["eft_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proof_file_id"], ["managed_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payment_id", name="uq_eft_provider_payment"),
        sa.UniqueConstraint("bank_reference"),
        sa.UniqueConstraint("instruction_reference"),
    )
    for column in ["payment_id", "configuration_id", "company_id", "bank_reference", "instruction_reference", "provider_status"]:
        op.create_index(f"ix_eft_provider_transactions_{column}", "eft_provider_transactions", [column])

    op.create_table(
        "transaction_charge_agreements",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_number", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("inbound_percentage", sa.Numeric(10, 6), nullable=False),
        sa.Column("outbound_percentage", sa.Numeric(10, 6), nullable=False),
        sa.Column("inbound_flat_fee", sa.Numeric(15, 2), nullable=False),
        sa.Column("outbound_flat_fee", sa.Numeric(15, 2), nullable=False),
        sa.Column("minimum_charge", sa.Numeric(15, 2), nullable=True),
        sa.Column("maximum_charge", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("settlement_frequency", sa.String(length=30), nullable=False),
        sa.Column("settlement_day", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("owner_accepted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_accepted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("company_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("agreement_number"),
    )
    for column in ["company_id", "agreement_number", "status"]:
        op.create_index(f"ix_transaction_charge_agreements_{column}", "transaction_charge_agreements", [column])

    op.create_table(
        "platform_charge_claims",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_number", sa.String(length=80), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("gross_transaction_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("disputed_at", sa.DateTime(), nullable=True),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agreement_id"], ["transaction_charge_agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("claim_number"),
    )
    for column in ["company_id", "agreement_id", "claim_number", "period_start", "period_end", "status"]:
        op.create_index(f"ix_platform_charge_claims_{column}", "platform_charge_claims", [column])

    payment_direction = postgresql.ENUM(name="paymentdirection", create_type=False)
    payment_provider = postgresql.ENUM(name="paymentprovider", create_type=False)
    op.create_table(
        "transaction_charge_ledger_entries",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", payment_direction, nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("payment_purpose", sa.String(length=80), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("percentage_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("flat_fee", sa.Numeric(15, 2), nullable=False),
        sa.Column("charge_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("accrued_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("waived_at", sa.DateTime(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agreement_id"], ["transaction_charge_agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["claim_id"], ["platform_charge_claims.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payment_id", name="uq_transaction_charge_payment"),
    )
    for column in ["company_id", "agreement_id", "payment_id", "claim_id", "direction", "provider", "payment_purpose", "status"]:
        op.create_index(f"ix_transaction_charge_ledger_entries_{column}", "transaction_charge_ledger_entries", [column])

    op.create_table(
        "platform_staff_profiles",
        *audit_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_title", sa.String(length=160), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", name="uq_platform_staff_user"),
    )
    op.create_index("ix_platform_staff_profiles_user_id", "platform_staff_profiles", ["user_id"])
    op.create_index("ix_platform_staff_profiles_is_active", "platform_staff_profiles", ["is_active"])


def downgrade():
    op.drop_index("ix_platform_staff_profiles_is_active", table_name="platform_staff_profiles")
    op.drop_index("ix_platform_staff_profiles_user_id", table_name="platform_staff_profiles")
    op.drop_table("platform_staff_profiles")

    for column in ["company_id", "agreement_id", "payment_id", "claim_id", "direction", "provider", "payment_purpose", "status"]:
        op.drop_index(f"ix_transaction_charge_ledger_entries_{column}", table_name="transaction_charge_ledger_entries")
    op.drop_table("transaction_charge_ledger_entries")

    for column in ["company_id", "agreement_id", "claim_number", "period_start", "period_end", "status"]:
        op.drop_index(f"ix_platform_charge_claims_{column}", table_name="platform_charge_claims")
    op.drop_table("platform_charge_claims")

    for column in ["company_id", "agreement_number", "status"]:
        op.drop_index(f"ix_transaction_charge_agreements_{column}", table_name="transaction_charge_agreements")
    op.drop_table("transaction_charge_agreements")

    for column in ["payment_id", "configuration_id", "company_id", "bank_reference", "instruction_reference", "provider_status"]:
        op.drop_index(f"ix_eft_provider_transactions_{column}", table_name="eft_provider_transactions")
    op.drop_table("eft_provider_transactions")

    for column in ["scope_key", "scope_type", "company_id", "is_active"]:
        op.drop_index(f"ix_eft_configurations_{column}", table_name="eft_configurations")
    op.drop_table("eft_configurations")

    for column in ["configuration_id", "provider_transaction_id", "payload_hash", "processing_status"]:
        op.drop_index(f"ix_ecocash_callback_events_{column}", table_name="ecocash_callback_events")
    op.drop_table("ecocash_callback_events")

    for column in [
        "payment_id", "configuration_id", "company_id", "borrower_id", "operation_type",
        "client_correlator", "reference_code", "provider_transaction_id",
        "original_provider_reference", "provider_status",
    ]:
        op.drop_index(f"ix_ecocash_provider_transactions_{column}", table_name="ecocash_provider_transactions")
    op.drop_table("ecocash_provider_transactions")

    for column in ["scope_key", "scope_type", "company_id", "is_active"]:
        op.drop_index(f"ix_ecocash_configurations_{column}", table_name="ecocash_configurations")
    op.drop_table("ecocash_configurations")

    op.drop_index("ix_borrower_fee_configurations_is_active", table_name="borrower_fee_configurations")
    op.drop_index("ix_borrower_fee_configurations_company_id", table_name="borrower_fee_configurations")
    op.drop_table("borrower_fee_configurations")

    op.drop_index("ix_loan_requests_service_fee_status", table_name="loan_requests")
    op.drop_index("ix_loan_requests_captured_by_user_id", table_name="loan_requests")
    op.drop_constraint("uq_loan_requests_service_fee_payment_id", "loan_requests", type_="unique")
    op.drop_constraint("fk_loan_requests_service_fee_payment_id", "loan_requests", type_="foreignkey")
    op.drop_constraint("fk_loan_requests_captured_by_user_id", "loan_requests", type_="foreignkey")
    for column in [
        "service_fee_payment_id", "service_fee_status", "service_fee_currency",
        "service_fee_amount", "captured_by_user_id", "origination_channel",
    ]:
        op.drop_column("loan_requests", column)

    op.drop_index("ix_payment_transactions_direct_application_id", table_name="payment_transactions")
    op.drop_constraint("fk_payment_transactions_direct_application_id", "payment_transactions", type_="foreignkey")
    op.drop_column("payment_transactions", "direct_application_id")

    op.drop_index("ix_mpesa_configurations_scope_type", table_name="mpesa_configurations")
    op.drop_index("ix_mpesa_configurations_scope_key", table_name="mpesa_configurations")
    op.drop_constraint("uq_mpesa_configuration_scope", "mpesa_configurations", type_="unique")
    op.alter_column("mpesa_configurations", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_unique_constraint("uq_mpesa_configuration_company", "mpesa_configurations", ["company_id"])
    op.drop_column("mpesa_configurations", "scope_type")
    op.drop_column("mpesa_configurations", "scope_key")

    op.drop_constraint("uq_company_staff_user_company_role", "company_staff", type_="unique")
    op.create_unique_constraint("uq_company_staff_user_company", "company_staff", ["user_id", "company_id"])
    op.drop_column("company_staff", "is_primary")
