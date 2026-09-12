"""maturity renewal cycles and recovery coordination

Revision ID: c2r6t8v0w132
Revises: b1q5s7u9v021
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2r6t8v0w132"
down_revision: Union[str, Sequence[str], None] = "b1q5s7u9v021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "maturity_renewal_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("rollover_basis", sa.String(length=40), server_default="outstanding_balance", nullable=False),
        sa.Column("reuse_original_rate", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("renewal_rate_percent", sa.Numeric(8, 3), nullable=True),
        sa.Column("reuse_original_term", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("renewal_term_months", sa.Integer(), nullable=True),
        sa.Column("include_processing_fee", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("grace_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_cycles", sa.Integer(), nullable=True),
        sa.Column("notify_borrower", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_maturity_renewal_policy_company"),
    )
    op.create_index("ix_maturity_renewal_policies_company_id", "maturity_renewal_policies", ["company_id"], unique=True)
    op.create_index("ix_maturity_renewal_policies_enabled", "maturity_renewal_policies", ["enabled"], unique=False)

    op.create_table(
        "loan_renewal_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("automatic", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("opening_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("rollover_basis", sa.String(length=40), server_default="outstanding_balance", nullable=False),
        sa.Column("rate_percent", sa.Numeric(8, 3), server_default="0", nullable=False),
        sa.Column("processing_fee", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("calculation_method", sa.String(length=40), nullable=False),
        sa.Column("installment_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_repayable", sa.Numeric(15, 2), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("rolled_at", sa.DateTime(), nullable=False),
        sa.Column("previous_terms_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("previous_schedule_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("calculation_breakdown", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id", "cycle_number", name="uq_loan_renewal_cycle_number"),
    )
    op.create_index("ix_loan_renewal_cycles_company_id", "loan_renewal_cycles", ["company_id"], unique=False)
    op.create_index("ix_loan_renewal_cycles_loan_id", "loan_renewal_cycles", ["loan_id"], unique=False)
    op.create_index("ix_loan_renewal_cycles_borrower_id", "loan_renewal_cycles", ["borrower_id"], unique=False)
    op.create_index("ix_loan_renewal_cycles_status", "loan_renewal_cycles", ["status"], unique=False)

    op.add_column("client_company_loan", sa.Column("automatic_renewal_enabled", sa.Boolean(), nullable=True))
    op.add_column("client_company_loan", sa.Column("renewal_cycle_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("client_company_loan", sa.Column("original_maturity_date", sa.Date(), nullable=True))
    op.add_column("client_company_loan", sa.Column("last_renewed_at", sa.DateTime(), nullable=True))
    op.add_column("client_company_loan", sa.Column("renewal_stopped_at", sa.DateTime(), nullable=True))
    op.add_column("client_company_loan", sa.Column("renewal_stopped_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("client_company_loan", sa.Column("renewal_stop_reason", sa.Text(), nullable=True))
    op.create_foreign_key("fk_client_company_loan_renewal_stopped_by_user_id_users", "client_company_loan", "users", ["renewal_stopped_by_user_id"], ["id"], ondelete="SET NULL")

    op.add_column("repayment_installments", sa.Column("renewal_cycle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("repayment_installments", sa.Column("superseded_by_cycle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("repayment_installments", sa.Column("is_superseded", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("repayment_installments", sa.Column("superseded_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_repayment_installments_renewal_cycle_id", "repayment_installments", "loan_renewal_cycles", ["renewal_cycle_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_repayment_installments_superseded_by_cycle_id", "repayment_installments", "loan_renewal_cycles", ["superseded_by_cycle_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_repayment_installments_renewal_cycle_id", "repayment_installments", ["renewal_cycle_id"], unique=False)
    op.create_index("ix_repayment_installments_superseded_by_cycle_id", "repayment_installments", ["superseded_by_cycle_id"], unique=False)
    op.create_index("ix_repayment_installments_is_superseded", "repayment_installments", ["is_superseded"], unique=False)

    # r1c2d3e4f510 creates collections tables from the live SQLAlchemy metadata.
    # On a fresh install that means these recovery-coordination columns can
    # already exist by the time this revision runs, while older deployed DBs
    # genuinely need this revision to add them. Keep the migration safe for
    # both histories instead of attempting the same ALTER TABLE twice.
    bind = op.get_bind()
    collection_columns = {column["name"] for column in sa.inspect(bind).get_columns("collection_cases")}
    claimed_by_added = "action_claimed_by_user_id" not in collection_columns
    claim_expires_added = "action_claim_expires_at" not in collection_columns

    if claimed_by_added:
        op.add_column("collection_cases", sa.Column("action_claimed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_collection_cases_action_claimed_by_user_id_users", "collection_cases", "users", ["action_claimed_by_user_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_collection_cases_action_claimed_by_user_id", "collection_cases", ["action_claimed_by_user_id"], unique=False)
    if "action_claimed_at" not in collection_columns:
        op.add_column("collection_cases", sa.Column("action_claimed_at", sa.DateTime(), nullable=True))
    if claim_expires_added:
        op.add_column("collection_cases", sa.Column("action_claim_expires_at", sa.DateTime(), nullable=True))
        op.create_index("ix_collection_cases_action_claim_expires_at", "collection_cases", ["action_claim_expires_at"], unique=False)


def downgrade() -> None:
    # Recovery claim columns are intentionally retained. The historical
    # r1c2d3e4f510 revision materialises collection_cases from current model
    # metadata on fresh databases, so those columns can belong to the older
    # schema there. They are additive coordination metadata and are safe to
    # retain on a rollback of only the maturity-renewal feature.

    op.drop_index("ix_repayment_installments_is_superseded", table_name="repayment_installments")
    op.drop_index("ix_repayment_installments_superseded_by_cycle_id", table_name="repayment_installments")
    op.drop_index("ix_repayment_installments_renewal_cycle_id", table_name="repayment_installments")
    op.drop_constraint("fk_repayment_installments_superseded_by_cycle_id", "repayment_installments", type_="foreignkey")
    op.drop_constraint("fk_repayment_installments_renewal_cycle_id", "repayment_installments", type_="foreignkey")
    op.drop_column("repayment_installments", "superseded_at")
    op.drop_column("repayment_installments", "is_superseded")
    op.drop_column("repayment_installments", "superseded_by_cycle_id")
    op.drop_column("repayment_installments", "renewal_cycle_id")

    op.drop_constraint("fk_client_company_loan_renewal_stopped_by_user_id_users", "client_company_loan", type_="foreignkey")
    op.drop_column("client_company_loan", "renewal_stop_reason")
    op.drop_column("client_company_loan", "renewal_stopped_by_user_id")
    op.drop_column("client_company_loan", "renewal_stopped_at")
    op.drop_column("client_company_loan", "last_renewed_at")
    op.drop_column("client_company_loan", "original_maturity_date")
    op.drop_column("client_company_loan", "renewal_cycle_count")
    op.drop_column("client_company_loan", "automatic_renewal_enabled")

    op.drop_index("ix_loan_renewal_cycles_status", table_name="loan_renewal_cycles")
    op.drop_index("ix_loan_renewal_cycles_borrower_id", table_name="loan_renewal_cycles")
    op.drop_index("ix_loan_renewal_cycles_loan_id", table_name="loan_renewal_cycles")
    op.drop_index("ix_loan_renewal_cycles_company_id", table_name="loan_renewal_cycles")
    op.drop_table("loan_renewal_cycles")

    op.drop_index("ix_maturity_renewal_policies_enabled", table_name="maturity_renewal_policies")
    op.drop_index("ix_maturity_renewal_policies_company_id", table_name="maturity_renewal_policies")
    op.drop_table("maturity_renewal_policies")
