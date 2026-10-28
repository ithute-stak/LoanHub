"""Add append-only compensating rollover reversal evidence.

Revision ID: r8l1c2m4f467
Revises: r8l1t2x3f467
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r8l1c2m4f467"
down_revision = "r8l1t2x3f467"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loan_rollover_compensations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=36)),
        sa.Column("updated_by", sa.String(length=36)),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_rollover_transfers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=False),
        sa.Column("approval_reference", sa.String(length=180), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("principal_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("interest_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("fee_component", sa.Numeric(15, 2), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("transfer_id", name="uq_rollover_compensation_once"),
        sa.UniqueConstraint("company_id", "reference", name="uq_rollover_compensation_reference"),
        sa.CheckConstraint("amount > 0", name="ck_rollover_compensation_positive"),
        sa.CheckConstraint("principal_component >= 0 AND interest_component >= 0 AND fee_component >= 0", name="ck_rollover_compensation_components_nonnegative"),
        sa.CheckConstraint("amount = principal_component + interest_component + fee_component", name="ck_rollover_compensation_balances"),
    )
    op.create_index("ix_loan_rollover_compensations_company_id", "loan_rollover_compensations", ["company_id"])
    op.execute("""
        CREATE TRIGGER trg_rollover_compensation_immutable
        BEFORE UPDATE OR DELETE ON loan_rollover_compensations
        FOR EACH ROW EXECUTE FUNCTION prevent_rollover_transfer_mutation()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_rollover_compensation_immutable ON loan_rollover_compensations")
    op.drop_index("ix_loan_rollover_compensations_company_id", table_name="loan_rollover_compensations")
    op.drop_table("loan_rollover_compensations")
