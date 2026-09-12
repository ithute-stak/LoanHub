"""Owner payment routing, assisted company clients and staff administration.

Revision ID: e7b2c4d9a610
Revises: c4f9e2d7a110
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7b2c4d9a610"
down_revision = "c4f9e2d7a110"
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
    # PostgreSQL enum labels are retained on downgrade because removing a label
    # safely requires recreating the enum type and every dependent column.
    op.execute(
        "ALTER TYPE paymentpurpose ADD VALUE IF NOT EXISTS "
        "'assisted_borrower_account_fee'"
    )

    for table_name, outbound_default, inbound_operation, outbound_operation in (
        ("mpesa_configurations", "true", "c2b_single", "b2c_single"),
        ("ecocash_configurations", "false", "charge", "refund"),
    ):
        op.add_column(
            table_name,
            sa.Column("inbound_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        )
        op.add_column(
            table_name,
            sa.Column(
                "outbound_enabled",
                sa.Boolean(),
                server_default=sa.text(outbound_default),
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "default_inbound_operation",
                sa.String(length=60),
                server_default=inbound_operation,
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "default_outbound_operation",
                sa.String(length=60),
                server_default=outbound_operation,
                nullable=False,
            ),
        )

    op.create_table(
        "company_account_opening_fee_configurations",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("fee_type", sa.String(length=20), nullable=False),
        sa.Column("flat_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(10, 6), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("maximum_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("required_before_activation", sa.Boolean(), nullable=False),
        sa.Column("allowed_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_company_account_opening_fee_configurations_company_id",
        "company_account_opening_fee_configurations",
        ["company_id"],
    )
    op.create_index(
        "ix_company_account_opening_fee_configurations_is_active",
        "company_account_opening_fee_configurations",
        ["is_active"],
    )

    op.create_table(
        "payment_routing_rules",
        *audit_columns(),
        sa.Column("scope_key", sa.String(length=100), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("direction", postgresql.ENUM(name="paymentdirection", create_type=False), nullable=False),
        sa.Column("provider", postgresql.ENUM(name="paymentprovider", create_type=False), nullable=False),
        sa.Column("configuration_scope", sa.String(length=20), nullable=False),
        sa.Column("provider_operation", sa.String(length=60), nullable=True),
        sa.Column("payer_scope", sa.String(length=30), nullable=False),
        sa.Column("recipient_scope", sa.String(length=30), nullable=False),
        sa.Column("requires_maker_checker", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scope_key", "purpose", name="uq_payment_routing_rule_scope_purpose"),
    )
    for column in ("scope_key", "scope_type", "company_id", "purpose", "direction", "provider", "is_active"):
        op.create_index(f"ix_payment_routing_rules_{column}", "payment_routing_rules", [column])

    op.create_table(
        "company_borrower_accounts",
        *audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opened_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_reference", sa.String(length=70), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("opening_fee_configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opening_fee_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("opening_fee_currency", sa.String(length=3), nullable=False),
        sa.Column("opening_fee_status", sa.String(length=30), nullable=False),
        sa.Column("opening_fee_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["opened_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["opening_fee_configuration_id"],
            ["company_account_opening_fee_configurations.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "company_id",
            "borrower_id",
            name="uq_company_borrower_account_company_borrower",
        ),
        sa.UniqueConstraint("account_reference", name="uq_company_borrower_account_reference"),
        sa.UniqueConstraint("opening_fee_payment_id", name="uq_company_borrower_account_fee_payment"),
    )
    for column in (
        "company_id",
        "branch_id",
        "borrower_id",
        "opened_by_user_id",
        "account_reference",
        "status",
        "opening_fee_configuration_id",
        "opening_fee_status",
    ):
        op.create_index(f"ix_company_borrower_accounts_{column}", "company_borrower_accounts", [column])

    op.add_column(
        "payment_transactions",
        sa.Column("company_borrower_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "payment_transactions",
        sa.Column("routing_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "payment_transactions",
        sa.Column("configuration_scope", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "payment_transactions",
        sa.Column("provider_operation", sa.String(length=60), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_transactions_company_borrower_account_id",
        "payment_transactions",
        "company_borrower_accounts",
        ["company_borrower_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_payment_transactions_routing_rule_id",
        "payment_transactions",
        "payment_routing_rules",
        ["routing_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_payment_transactions_company_borrower_account_id",
        "payment_transactions",
        ["company_borrower_account_id"],
    )
    op.create_index(
        "ix_payment_transactions_routing_rule_id",
        "payment_transactions",
        ["routing_rule_id"],
    )
    op.create_foreign_key(
        "fk_company_borrower_accounts_opening_fee_payment_id",
        "company_borrower_accounts",
        "payment_transactions",
        ["opening_fee_payment_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    op.add_column(
        "direct_loan_applications",
        sa.Column("captured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_direct_loan_applications_captured_by_user_id",
        "direct_loan_applications",
        "users",
        ["captured_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_direct_loan_applications_captured_by_user_id",
        "direct_loan_applications",
        ["captured_by_user_id"],
    )


def downgrade():
    op.drop_index("ix_direct_loan_applications_captured_by_user_id", table_name="direct_loan_applications")
    op.drop_constraint(
        "fk_direct_loan_applications_captured_by_user_id",
        "direct_loan_applications",
        type_="foreignkey",
    )
    op.drop_column("direct_loan_applications", "captured_by_user_id")

    op.drop_constraint(
        "fk_company_borrower_accounts_opening_fee_payment_id",
        "company_borrower_accounts",
        type_="foreignkey",
    )
    op.drop_index("ix_payment_transactions_routing_rule_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_company_borrower_account_id", table_name="payment_transactions")
    op.drop_constraint("fk_payment_transactions_routing_rule_id", "payment_transactions", type_="foreignkey")
    op.drop_constraint(
        "fk_payment_transactions_company_borrower_account_id",
        "payment_transactions",
        type_="foreignkey",
    )
    op.drop_column("payment_transactions", "provider_operation")
    op.drop_column("payment_transactions", "configuration_scope")
    op.drop_column("payment_transactions", "routing_rule_id")
    op.drop_column("payment_transactions", "company_borrower_account_id")

    op.drop_table("company_borrower_accounts")
    op.drop_table("payment_routing_rules")
    op.drop_table("company_account_opening_fee_configurations")

    for table_name in ("ecocash_configurations", "mpesa_configurations"):
        op.drop_column(table_name, "default_outbound_operation")
        op.drop_column(table_name, "default_inbound_operation")
        op.drop_column(table_name, "outbound_enabled")
        op.drop_column(table_name, "inbound_enabled")
