"""multitenant SaaS, billing, payments and repayment foundation

Revision ID: 9f1c2d3e4a5b
Revises: 7ba90e8af6b6
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f1c2d3e4a5b"
down_revision: Union[str, Sequence[str], None] = "7ba90e8af6b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


billing_cycle_enum = postgresql.ENUM(
    "MONTHLY",
    "ANNUAL",
    "PAY_PER_TRANSACTION",
    name="billingcycle",
    create_type=False,
)
payment_provider_enum = postgresql.ENUM(
    "MPESA",
    "ECOCASH",
    "MANUAL",
    "MOCK",
    name="paymentprovider",
    create_type=False,
)
payment_status_enum = postgresql.ENUM(
    "PENDING",
    "PROCESSING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "REVERSED",
    name="paymentstatus",
    create_type=False,
)
payment_direction_enum = postgresql.ENUM(
    "INBOUND",
    "OUTBOUND",
    name="paymentdirection",
    create_type=False,
)
payment_purpose_enum = postgresql.ENUM(
    "SUBSCRIPTION",
    "MARKETPLACE_UNLOCK",
    "LOAN_DISBURSEMENT",
    "LOAN_REPAYMENT",
    "PLATFORM_FEE",
    "REFUND",
    name="paymentpurpose",
    create_type=False,
)
unlock_status_enum = postgresql.ENUM(
    "PENDING",
    "UNLOCKED",
    "FAILED",
    "REVOKED",
    name="unlockstatus",
    create_type=False,
)
installment_status_enum = postgresql.ENUM(
    "PENDING",
    "PARTIALLY_PAID",
    "PAID",
    "OVERDUE",
    "WAIVED",
    name="installmentstatus",
    create_type=False,
)


def _add_enum_value(type_name: str, value: str) -> None:
    escaped_type = type_name.replace('"', '""')
    escaped_value = value.replace("'", "''")
    op.execute(
        sa.text(
            f"ALTER TYPE \"{escaped_type}\" ADD VALUE IF NOT EXISTS '{escaped_value}'"
        )
    )


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    connection = op.get_bind()

    # Extend existing PostgreSQL enum types without recreating them.
    for role in (
        "COMPANY_OWNER",
        "FINANCE_OFFICER",
        "COLLECTIONS_OFFICER",
        "COMPLIANCE_OFFICER",
        "AUDITOR",
        "CUSTOMER_SUPPORT",
    ):
        _add_enum_value("userrole", role)

    _add_enum_value("loanrequeststatus", "OPEN")
    _add_enum_value("offerstatus", "EXPIRED")
    _add_enum_value("subscriptionstatus", "SUSPENDED")
    _add_enum_value("loanstatus", "cancelled")

    # New enum types.
    for enum_type in (
        billing_cycle_enum,
        payment_provider_enum,
        payment_status_enum,
        payment_direction_enum,
        payment_purpose_enum,
        unlock_status_enum,
        installment_status_enum,
    ):
        enum_type.create(connection, checkfirst=True)

    # Existing tenant data integrity.
    connection.execute(sa.text("UPDATE loan_companies SET status = 'PENDING' WHERE status IS NULL"))
    connection.execute(sa.text("UPDATE loan_companies SET is_active = FALSE WHERE is_active IS NULL"))
    connection.execute(sa.text("UPDATE company_branches SET is_active = TRUE WHERE is_active IS NULL"))
    connection.execute(sa.text("UPDATE company_staff SET is_active = TRUE WHERE is_active IS NULL"))

    op.alter_column("loan_companies", "status", existing_type=postgresql.ENUM(name="companystatus", create_type=False), nullable=False)
    op.alter_column("loan_companies", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.alter_column("company_branches", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.alter_column("company_staff", "is_active", existing_type=sa.Boolean(), nullable=False)

    op.create_unique_constraint("uq_company_branch_name", "company_branches", ["company_id", "name"])
    op.create_unique_constraint("uq_company_staff_user_company", "company_staff", ["user_id", "company_id"])
    op.create_index("ix_company_branches_company_id", "company_branches", ["company_id"], unique=False)
    op.create_index("ix_company_staff_company_id", "company_staff", ["company_id"], unique=False)
    op.create_index("ix_company_staff_branch_id", "company_staff", ["branch_id"], unique=False)
    op.create_index("ix_company_staff_user_id", "company_staff", ["user_id"], unique=False)

    # Company-managed loan product catalogue.
    connection.execute(sa.text("UPDATE loan_products SET processing_fee = 0 WHERE processing_fee IS NULL"))
    connection.execute(sa.text("UPDATE loan_products SET interest_rate_percent = 0 WHERE interest_rate_percent IS NULL"))
    connection.execute(sa.text("UPDATE loan_products SET is_active = TRUE WHERE is_active IS NULL"))
    op.alter_column("loan_products", "interest_rate_percent", existing_type=sa.Numeric(5, 2), type_=sa.Numeric(6, 3), nullable=False)
    op.alter_column("loan_products", "processing_fee", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column("loan_products", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.create_index("ix_loan_products_company_id", "loan_products", ["company_id"], unique=False)

    # Marketplace request lifecycle.
    connection.execute(sa.text("UPDATE loan_requests SET status = 'SUBMITTED' WHERE status IS NULL"))
    connection.execute(sa.text("UPDATE loan_requests SET visible_to_lenders = FALSE WHERE visible_to_lenders IS NULL"))
    connection.execute(sa.text("UPDATE loan_requests SET allow_lenders_to_call = TRUE WHERE allow_lenders_to_call IS NULL"))
    op.alter_column("loan_requests", "status", existing_type=postgresql.ENUM(name="loanrequeststatus", create_type=False), nullable=False)
    op.alter_column("loan_requests", "visible_to_lenders", existing_type=sa.Boolean(), nullable=False)
    op.alter_column("loan_requests", "allow_lenders_to_call", existing_type=sa.Boolean(), nullable=False)
    op.add_column("loan_requests", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    op.add_column("loan_requests", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("loan_requests", sa.Column("accepted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_loan_requests_status", "loan_requests", ["status"], unique=False)
    op.create_index("ix_loan_requests_expires_at", "loan_requests", ["expires_at"], unique=False)
    op.create_index("ix_loan_requests_borrower_id", "loan_requests", ["borrower_id"], unique=False)
    op.create_unique_constraint("uq_loan_requests_selected_offer", "loan_requests", ["selected_offer_id"])

    # Offer integrity and calculated values.
    connection.execute(
        sa.text(
            """
            UPDATE loan_offers
            SET interest_rate_percent = COALESCE(interest_rate_percent, 0),
                processing_fee = COALESCE(processing_fee, 0),
                total_repayment = COALESCE(
                    total_repayment,
                    approved_amount
                    + (approved_amount * COALESCE(interest_rate_percent, 0) / 100 * term_months / 12)
                    + COALESCE(processing_fee, 0)
                )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE loan_offers
            SET monthly_repayment = COALESCE(monthly_repayment, total_repayment / NULLIF(term_months, 0)),
                status = COALESCE(status, 'PENDING')
            """
        )
    )
    op.alter_column("loan_offers", "interest_rate_percent", existing_type=sa.Numeric(5, 2), type_=sa.Numeric(6, 3), nullable=False)
    op.alter_column("loan_offers", "processing_fee", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column("loan_offers", "monthly_repayment", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column("loan_offers", "total_repayment", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column("loan_offers", "status", existing_type=postgresql.ENUM(name="offerstatus", create_type=False), nullable=False)
    op.add_column("loan_offers", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("loan_offers", sa.Column("accepted_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_loan_offer_request_company", "loan_offers", ["loan_request_id", "company_id"])
    op.create_index("ix_loan_offers_request_id", "loan_offers", ["loan_request_id"], unique=False)
    op.create_index("ix_loan_offers_company_id", "loan_offers", ["company_id"], unique=False)
    op.create_index("ix_loan_offers_branch_id", "loan_offers", ["branch_id"], unique=False)
    op.create_index("ix_loan_offers_status", "loan_offers", ["status"], unique=False)

    # Subscription plans and richer company subscriptions.
    op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("monthly_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("annual_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("marketplace_unlock_fee", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_fee_percent", sa.Numeric(6, 3), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        *_base_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"], unique=True)

    # Use literal PostgreSQL SQL instead of ``op.bulk_insert`` with JSONB.
    # Alembic cannot render Python dict values in ``upgrade --sql`` mode.
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_plans (
                id,
                code,
                name,
                description,
                monthly_price,
                annual_price,
                marketplace_unlock_fee,
                transaction_fee_percent,
                features,
                limits,
                is_active,
                is_public
            )
            VALUES
                (
                    '00000000-0000-4000-8000-000000000001'::uuid,
                    'STARTER',
                    'Starter',
                    'Pay per marketplace unlock for smaller lenders.',
                    0,
                    0,
                    25,
                    1.5,
                    '{"marketplace_full_access": false}'::jsonb,
                    '{"branches": 1, "staff": 5, "products": 3}'::jsonb,
                    TRUE,
                    TRUE
                ),
                (
                    '00000000-0000-4000-8000-000000000002'::uuid,
                    'GROWTH',
                    'Growth',
                    'Monthly access for growing multi-branch lenders.',
                    799,
                    7990,
                    0,
                    1.0,
                    '{"marketplace_full_access": true}'::jsonb,
                    '{"branches": 10, "staff": 50, "products": 25}'::jsonb,
                    TRUE,
                    TRUE
                ),
                (
                    '00000000-0000-4000-8000-000000000003'::uuid,
                    'ENTERPRISE',
                    'Enterprise',
                    'Unlimited company operations and advanced controls.',
                    1999,
                    19990,
                    0,
                    0.5,
                    '{
                        "marketplace_full_access": true,
                        "priority_support": true
                    }'::jsonb,
                    '{"branches": -1, "staff": -1, "products": -1}'::jsonb,
                    TRUE,
                    TRUE
                )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    op.add_column("company_subscriptions", sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("company_subscriptions", sa.Column("billing_cycle", billing_cycle_enum, nullable=True))
    op.add_column("company_subscriptions", sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("company_subscriptions", sa.Column("payment_provider", payment_provider_enum, nullable=True))
    op.add_column("company_subscriptions", sa.Column("external_reference", sa.String(length=160), nullable=True))
    connection.execute(sa.text("UPDATE company_subscriptions SET status = 'PENDING' WHERE status IS NULL"))
    connection.execute(sa.text("UPDATE company_subscriptions SET billing_cycle = 'MONTHLY' WHERE billing_cycle IS NULL"))
    op.alter_column("company_subscriptions", "status", existing_type=postgresql.ENUM(name="subscriptionstatus", create_type=False), nullable=False)
    op.alter_column("company_subscriptions", "billing_cycle", existing_type=billing_cycle_enum, nullable=False)
    op.create_foreign_key("fk_company_subscription_plan", "company_subscriptions", "subscription_plans", ["plan_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_company_subscriptions_company_id", "company_subscriptions", ["company_id"], unique=False)
    op.create_index("ix_company_subscriptions_plan_id", "company_subscriptions", ["plan_id"], unique=False)
    op.create_unique_constraint("uq_company_subscription_external_reference", "company_subscriptions", ["external_reference"])

    # Improve the accepted-loan record.
    op.execute(sa.text("ALTER TABLE client_company_loan DROP CONSTRAINT IF EXISTS client_company_loan_created_by_fkey"))
    op.execute(sa.text("ALTER TABLE client_company_loan DROP CONSTRAINT IF EXISTS client_company_loan_approved_by_fkey"))
    op.alter_column(
        "client_company_loan",
        "created_by",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=36),
        existing_nullable=True,
        postgresql_using="created_by::text",
    )
    op.drop_column("client_company_loan", "approved_by")
    op.add_column("client_company_loan", sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("client_company_loan", sa.Column("processing_fee", sa.Numeric(15, 2), nullable=False, server_default="0"))
    op.add_column("client_company_loan", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("client_company_loan", sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("client_company_loan", sa.Column("disbursed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    connection.execute(sa.text("UPDATE client_company_loan SET loan_reference = 'LH-MIGRATED-' || UPPER(SUBSTRING(id::text, 1, 8)) WHERE loan_reference IS NULL"))
    connection.execute(sa.text("UPDATE client_company_loan SET amount_paid = 0 WHERE amount_paid IS NULL"))
    connection.execute(sa.text("UPDATE client_company_loan SET status = 'pending' WHERE status IS NULL"))
    connection.execute(sa.text("UPDATE client_company_loan SET risk_level = 'low' WHERE risk_level IS NULL"))
    connection.execute(sa.text("UPDATE client_company_loan SET is_overdue = FALSE WHERE is_overdue IS NULL"))
    connection.execute(sa.text("UPDATE client_company_loan SET created_at = NOW() WHERE created_at IS NULL"))
    op.alter_column("client_company_loan", "loan_reference", existing_type=sa.String(50), nullable=False)
    op.alter_column("client_company_loan", "interest_rate", existing_type=sa.Numeric(5, 2), type_=sa.Numeric(6, 3), nullable=False)
    op.alter_column("client_company_loan", "amount_paid", existing_type=sa.Numeric(15, 2), nullable=False)
    op.alter_column("client_company_loan", "status", existing_type=postgresql.ENUM(name="loanstatus", create_type=False), nullable=False)
    op.alter_column("client_company_loan", "risk_level", existing_type=postgresql.ENUM(name="risklevel", create_type=False), nullable=False)
    op.alter_column("client_company_loan", "is_overdue", existing_type=sa.Boolean(), nullable=False)
    op.alter_column("client_company_loan", "created_at", existing_type=sa.DateTime(), nullable=False)
    op.create_foreign_key("fk_client_loan_branch", "client_company_loan", "company_branches", ["branch_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_client_loan_approved_by", "client_company_loan", "users", ["approved_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_client_loan_disbursed_by", "client_company_loan", "users", ["disbursed_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_client_loan_request", "client_company_loan", ["loan_request_id"])
    op.create_unique_constraint("uq_client_loan_offer", "client_company_loan", ["loan_offer_id"])
    op.create_index("ix_client_loan_company_id", "client_company_loan", ["company_id"], unique=False)
    op.create_index("ix_client_loan_branch_id", "client_company_loan", ["branch_id"], unique=False)
    op.create_index("ix_client_loan_borrower_id", "client_company_loan", ["borrower_id"], unique=False)

    # Payment ledger.
    op.create_table(
        "payment_transactions",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", payment_provider_enum, nullable=False),
        sa.Column("direction", payment_direction_enum, nullable=False),
        sa.Column("purpose", payment_purpose_enum, nullable=False),
        sa.Column("status", payment_status_enum, nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payer_phone", sa.String(length=30), nullable=True),
        sa.Column("payee_phone", sa.String(length=30), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("provider_reference", sa.String(length=180), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_request_id"], ["loan_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_reference"),
    )
    op.create_index("ix_payment_company_id", "payment_transactions", ["company_id"], unique=False)
    op.create_index("ix_payment_borrower_id", "payment_transactions", ["borrower_id"], unique=False)
    op.create_index("ix_payment_loan_request_id", "payment_transactions", ["loan_request_id"], unique=False)
    op.create_index("ix_payment_loan_id", "payment_transactions", ["loan_id"], unique=False)
    op.create_index("ix_payment_idempotency", "payment_transactions", ["idempotency_key"], unique=True)
    op.create_index("ix_payment_provider_reference", "payment_transactions", ["provider_reference"], unique=True)

    # Pay-per-request marketplace access.
    op.create_table(
        "marketplace_unlocks",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unlocked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("price_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", unlock_status_enum, nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_request_id"], ["loan_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unlocked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "loan_request_id", name="uq_marketplace_unlock_company_request"),
        sa.UniqueConstraint("payment_transaction_id"),
    )
    op.create_index("ix_marketplace_unlock_company", "marketplace_unlocks", ["company_id"], unique=False)
    op.create_index("ix_marketplace_unlock_request", "marketplace_unlocks", ["loan_request_id"], unique=False)

    # Repayment schedule and allocations.
    op.create_table(
        "repayment_installments",
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("principal_due", sa.Numeric(15, 2), nullable=False),
        sa.Column("interest_due", sa.Numeric(15, 2), nullable=False),
        sa.Column("fee_due", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_due", sa.Numeric(15, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", installment_status_enum, nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id", "installment_number", name="uq_repayment_installment_loan_number"),
    )
    op.create_index("ix_repayment_installment_loan", "repayment_installments", ["loan_id"], unique=False)
    op.create_index("ix_repayment_installment_due", "repayment_installments", ["due_date"], unique=False)

    op.create_table(
        "payment_allocations",
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        *_base_columns(),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installment_id"], ["repayment_installments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", "installment_id", name="uq_payment_allocation_payment_installment"),
    )
    op.create_index("ix_payment_allocation_payment", "payment_allocations", ["payment_id"], unique=False)
    op.create_index("ix_payment_allocation_installment", "payment_allocations", ["installment_id"], unique=False)


def downgrade() -> None:
    # This downgrade intentionally removes only the new SaaS tables/columns. PostgreSQL
    # enum values cannot be safely removed without rebuilding each enum type.
    op.drop_index("ix_payment_allocation_installment", table_name="payment_allocations")
    op.drop_index("ix_payment_allocation_payment", table_name="payment_allocations")
    op.drop_table("payment_allocations")

    op.drop_index("ix_repayment_installment_due", table_name="repayment_installments")
    op.drop_index("ix_repayment_installment_loan", table_name="repayment_installments")
    op.drop_table("repayment_installments")

    op.drop_index("ix_marketplace_unlock_request", table_name="marketplace_unlocks")
    op.drop_index("ix_marketplace_unlock_company", table_name="marketplace_unlocks")
    op.drop_table("marketplace_unlocks")

    op.drop_index("ix_payment_provider_reference", table_name="payment_transactions")
    op.drop_index("ix_payment_idempotency", table_name="payment_transactions")
    op.drop_index("ix_payment_loan_id", table_name="payment_transactions")
    op.drop_index("ix_payment_loan_request_id", table_name="payment_transactions")
    op.drop_index("ix_payment_borrower_id", table_name="payment_transactions")
    op.drop_index("ix_payment_company_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")

    op.drop_index("ix_client_loan_borrower_id", table_name="client_company_loan")
    op.drop_index("ix_client_loan_branch_id", table_name="client_company_loan")
    op.drop_index("ix_client_loan_company_id", table_name="client_company_loan")
    op.drop_constraint("uq_client_loan_offer", "client_company_loan", type_="unique")
    op.drop_constraint("uq_client_loan_request", "client_company_loan", type_="unique")
    op.drop_constraint("fk_client_loan_disbursed_by", "client_company_loan", type_="foreignkey")
    op.drop_constraint("fk_client_loan_approved_by", "client_company_loan", type_="foreignkey")
    op.drop_constraint("fk_client_loan_branch", "client_company_loan", type_="foreignkey")
    op.drop_column("client_company_loan", "disbursed_by_user_id")
    op.drop_column("client_company_loan", "approved_by_user_id")
    op.drop_column("client_company_loan", "approved_at")
    op.drop_column("client_company_loan", "processing_fee")
    op.drop_column("client_company_loan", "branch_id")

    op.drop_constraint("uq_company_subscription_external_reference", "company_subscriptions", type_="unique")
    op.drop_index("ix_company_subscriptions_plan_id", table_name="company_subscriptions")
    op.drop_index("ix_company_subscriptions_company_id", table_name="company_subscriptions")
    op.drop_constraint("fk_company_subscription_plan", "company_subscriptions", type_="foreignkey")
    op.drop_column("company_subscriptions", "external_reference")
    op.drop_column("company_subscriptions", "payment_provider")
    op.drop_column("company_subscriptions", "auto_renew")
    op.drop_column("company_subscriptions", "billing_cycle")
    op.drop_column("company_subscriptions", "plan_id")

    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_table("subscription_plans")

    op.drop_index("ix_loan_offers_status", table_name="loan_offers")
    op.drop_index("ix_loan_offers_branch_id", table_name="loan_offers")
    op.drop_index("ix_loan_offers_company_id", table_name="loan_offers")
    op.drop_index("ix_loan_offers_request_id", table_name="loan_offers")
    op.drop_constraint("uq_loan_offer_request_company", "loan_offers", type_="unique")
    op.drop_column("loan_offers", "accepted_at")
    op.drop_column("loan_offers", "expires_at")

    op.drop_constraint("uq_loan_requests_selected_offer", "loan_requests", type_="unique")
    op.drop_index("ix_loan_requests_borrower_id", table_name="loan_requests")
    op.drop_index("ix_loan_requests_expires_at", table_name="loan_requests")
    op.drop_index("ix_loan_requests_status", table_name="loan_requests")
    op.drop_column("loan_requests", "accepted_at")
    op.drop_column("loan_requests", "expires_at")
    op.drop_column("loan_requests", "submitted_at")

    op.drop_index("ix_company_staff_user_id", table_name="company_staff")
    op.drop_index("ix_company_staff_branch_id", table_name="company_staff")
    op.drop_index("ix_loan_products_company_id", table_name="loan_products")
    op.alter_column("loan_products", "is_active", existing_type=sa.Boolean(), nullable=True)
    op.alter_column("loan_products", "processing_fee", existing_type=sa.Numeric(12, 2), nullable=True)
    op.alter_column("loan_products", "interest_rate_percent", existing_type=sa.Numeric(6, 3), type_=sa.Numeric(5, 2), nullable=True)

    op.drop_index("ix_company_staff_company_id", table_name="company_staff")
    op.drop_index("ix_company_branches_company_id", table_name="company_branches")
    op.drop_constraint("uq_company_staff_user_company", "company_staff", type_="unique")
    op.drop_constraint("uq_company_branch_name", "company_branches", type_="unique")

    connection = op.get_bind()
    for enum_type in (
        installment_status_enum,
        unlock_status_enum,
        payment_purpose_enum,
        payment_direction_enum,
        payment_status_enum,
        payment_provider_enum,
        billing_cycle_enum,
    ):
        enum_type.drop(connection, checkfirst=True)
