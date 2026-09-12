"""M-Pesa OpenAPI integration and provider audit records.

Revision ID: b8d5e21f9a30
Revises: a7c91d2e4f10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8d5e21f9a30"
down_revision = "a7c91d2e4f10"
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
    # PostgreSQL enum values are append-only in this release. The downgrade keeps
    # the value because removing an enum value safely requires recreating the type.
    op.execute("ALTER TYPE paymentpurpose ADD VALUE IF NOT EXISTS 'business_payment'")

    op.create_table(
        "mpesa_configurations",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("market", sa.String(length=30), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("service_provider_code", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=255), nullable=False),
        sa.Column("callback_base_url", sa.String(length=500), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("encrypted_public_key", sa.Text(), nullable=False),
        sa.Column("session_lifetime_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled_products", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("production_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_connection_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_connection_test_status", sa.String(length=30), nullable=True),
        sa.Column("last_connection_test_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", name="uq_mpesa_configuration_company"),
    )
    op.create_index("ix_mpesa_configurations_company_id", "mpesa_configurations", ["company_id"])
    op.create_index("ix_mpesa_configurations_is_active", "mpesa_configurations", ["is_active"])

    op.create_table(
        "mpesa_provider_transactions",
        *audit_columns(),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_type", sa.String(length=60), nullable=False),
        sa.Column("third_party_conversation_id", sa.String(length=40), nullable=False),
        sa.Column("conversation_id", sa.String(length=80), nullable=True),
        sa.Column("transaction_id", sa.String(length=80), nullable=True),
        sa.Column("original_transaction_id", sa.String(length=80), nullable=True),
        sa.Column("query_reference", sa.String(length=80), nullable=True),
        sa.Column("provider_status", sa.String(length=50), nullable=False),
        sa.Column("response_code", sa.String(length=30), nullable=True),
        sa.Column("response_description", sa.Text(), nullable=True),
        sa.Column("is_reversed", sa.Boolean(), nullable=False),
        sa.Column("sanitized_request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("callback_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("status_query_count", sa.Integer(), nullable=False),
        sa.Column("last_status_check_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payment_id", name="uq_mpesa_provider_transaction_payment"),
        sa.UniqueConstraint("third_party_conversation_id", name="uq_mpesa_third_party_conversation"),
    )
    for column in ["payment_id", "company_id", "borrower_id", "operation_type", "third_party_conversation_id", "conversation_id", "transaction_id", "original_transaction_id", "query_reference", "provider_status", "response_code"]:
        op.create_index(f"ix_mpesa_provider_transactions_{column}", "mpesa_provider_transactions", [column])

    op.create_table(
        "mpesa_callback_events",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_status", sa.String(length=30), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_transaction_id"], ["mpesa_provider_transactions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payload_hash", name="uq_mpesa_callback_payload_hash"),
    )
    for column in ["company_id", "provider_transaction_id", "event_type", "payload_hash", "processing_status"]:
        op.create_index(f"ix_mpesa_callback_events_{column}", "mpesa_callback_events", [column])

    op.create_table(
        "mpesa_beneficiary_verifications",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("beneficiary_msisdn", sa.String(length=30), nullable=False),
        sa.Column("beneficiary_name", sa.String(length=255), nullable=True),
        sa.Column("provider_reference", sa.String(length=100), nullable=True),
        sa.Column("response_code", sa.String(length=30), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ["company_id", "requested_by_user_id", "beneficiary_msisdn", "provider_reference"]:
        op.create_index(f"ix_mpesa_beneficiary_verifications_{column}", "mpesa_beneficiary_verifications", [column])

    op.create_table(
        "mpesa_direct_debit_mandates",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_msisdn", sa.String(length=30), nullable=False),
        sa.Column("provider_mandate_reference", sa.String(length=100), nullable=True),
        sa.Column("third_party_conversation_id", sa.String(length=40), nullable=False),
        sa.Column("frequency", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=False),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("provider_mandate_reference", name="uq_mpesa_provider_mandate_reference"),
        sa.UniqueConstraint("third_party_conversation_id"),
    )
    for column in ["company_id", "borrower_id", "loan_id", "provider_mandate_reference", "third_party_conversation_id", "status"]:
        op.create_index(f"ix_mpesa_direct_debit_mandates_{column}", "mpesa_direct_debit_mandates", [column])

    op.create_table(
        "mpesa_reversal_requests",
        *audit_columns(),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("provider_reference", sa.String(length=100), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ["payment_id", "company_id", "status", "provider_reference"]:
        op.create_index(f"ix_mpesa_reversal_requests_{column}", "mpesa_reversal_requests", [column])


def downgrade():
    op.drop_table("mpesa_reversal_requests")
    op.drop_table("mpesa_direct_debit_mandates")
    op.drop_table("mpesa_beneficiary_verifications")
    op.drop_table("mpesa_callback_events")
    op.drop_table("mpesa_provider_transactions")
    op.drop_table("mpesa_configurations")
