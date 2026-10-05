"""Move CDAS credential custody to platform scope and add PAYG metering.

Revision ID: b9d3f5g7h911
Revises: a8c2e4f6g810
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b9d3f5g7h911"
down_revision = "a8c2e4f6g810"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "platform_cdas_subscriptions",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("pricing", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("warning_threshold", sa.Numeric(15, 2), nullable=True),
        sa.Column("auto_suspend_on_limit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_platform_cdas_subscription_company"),
    )
    op.create_index("ix_platform_cdas_subscriptions_company_id", "platform_cdas_subscriptions", ["company_id"])
    op.create_index("ix_platform_cdas_subscriptions_status", "platform_cdas_subscriptions", ["status"])

    op.create_table(
        "platform_cdas_credential_profiles",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("username", sa.String(length=200), nullable=False),
        sa.Column("item_code", sa.String(length=100), nullable=True),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Numeric(8, 2), nullable=False, server_default="20"),
        sa.Column("last_test_status", sa.String(length=60), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "environment", name="uq_platform_cdas_profile_company_environment"),
        sa.UniqueConstraint("environment", "username", name="uq_platform_cdas_profile_environment_username"),
    )
    op.create_index("ix_platform_cdas_profiles_company_id", "platform_cdas_credential_profiles", ["company_id"])
    op.create_index("ix_platform_cdas_profiles_environment", "platform_cdas_credential_profiles", ["environment"])

    op.create_table(
        "platform_cdas_transactions",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("operation_type", sa.String(length=80), nullable=False),
        sa.Column("billing_key", sa.String(length=180), nullable=False),
        sa.Column("transaction_reference", sa.String(length=100), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="accrued"),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference", sa.String(length=180), nullable=True),
        sa.Column("accrued_at", sa.DateTime(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("waived_at", sa.DateTime(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["platform_cdas_subscriptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("billing_key", name="uq_platform_cdas_transaction_billing_key"),
    )
    op.create_index("ix_platform_cdas_transactions_company_id", "platform_cdas_transactions", ["company_id"])
    op.create_index("ix_platform_cdas_transactions_subscription_id", "platform_cdas_transactions", ["subscription_id"])
    op.create_index("ix_platform_cdas_transactions_environment", "platform_cdas_transactions", ["environment"])
    op.create_index("ix_platform_cdas_transactions_operation_type", "platform_cdas_transactions", ["operation_type"])
    op.create_index("ix_platform_cdas_transactions_billing_key", "platform_cdas_transactions", ["billing_key"], unique=True)
    op.create_index("ix_platform_cdas_transactions_reference", "platform_cdas_transactions", ["transaction_reference"], unique=True)
    op.create_index("ix_platform_cdas_transactions_status", "platform_cdas_transactions", ["status"])
    op.create_index("ix_platform_cdas_transactions_source_reference", "platform_cdas_transactions", ["source_reference"])

    # Existing CDAS-enabled tenants retain access: their company-specific account
    # is adopted into platform custody and their existing enabled state becomes
    # an approved subscription with zero pricing until the Platform Owner sets rates.
    op.execute(
        """
        INSERT INTO platform_cdas_subscriptions (
            id, created_at, updated_at, company_id, status, currency, pricing,
            auto_suspend_on_limit, requested_at, reviewed_at, approved_at
        )
        SELECT
            gen_random_uuid(), now(), now(), company_id,
            CASE WHEN is_enabled THEN 'approved' ELSE 'pending' END,
            'LSL', '{}'::jsonb, true, now(),
            CASE WHEN is_enabled THEN now() ELSE NULL END,
            CASE WHEN is_enabled THEN now() ELSE NULL END
        FROM origination_integration_configurations
        WHERE provider = 'cdas'
        ON CONFLICT (company_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO platform_cdas_credential_profiles (
            id, created_at, updated_at, company_id, environment, base_url,
            username, item_code, encrypted_password, timeout_seconds,
            last_test_status, last_tested_at, configured_by_user_id
        )
        SELECT
            gen_random_uuid(), now(), now(), company_id,
            CASE WHEN lower(environment) = 'live' THEN 'live' ELSE 'test' END,
            configuration->>'base_url',
            configuration->>'username',
            NULLIF(configuration->>'item_code', ''),
            encrypted_credentials,
            COALESCE(NULLIF(configuration->>'timeout_seconds','')::numeric, 20),
            last_test_status, last_tested_at, configured_by_user_id
        FROM origination_integration_configurations
        WHERE provider = 'cdas'
          AND encrypted_credentials IS NOT NULL
          AND COALESCE(configuration->>'base_url','') <> ''
          AND COALESCE(configuration->>'username','') <> ''
        ON CONFLICT (company_id, environment) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE origination_integration_configurations
        SET
            configuration = jsonb_build_object('selected_environment',
                CASE WHEN lower(environment) = 'live' THEN 'live' ELSE 'test' END),
            encrypted_credentials = NULL,
            configured_by_user_id = NULL
        WHERE provider = 'cdas'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_platform_cdas_transactions_source_reference", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_status", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_reference", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_billing_key", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_operation_type", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_environment", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_subscription_id", table_name="platform_cdas_transactions")
    op.drop_index("ix_platform_cdas_transactions_company_id", table_name="platform_cdas_transactions")
    op.drop_table("platform_cdas_transactions")

    op.drop_index("ix_platform_cdas_profiles_environment", table_name="platform_cdas_credential_profiles")
    op.drop_index("ix_platform_cdas_profiles_company_id", table_name="platform_cdas_credential_profiles")
    op.drop_table("platform_cdas_credential_profiles")

    op.drop_index("ix_platform_cdas_subscriptions_status", table_name="platform_cdas_subscriptions")
    op.drop_index("ix_platform_cdas_subscriptions_company_id", table_name="platform_cdas_subscriptions")
    op.drop_table("platform_cdas_subscriptions")
