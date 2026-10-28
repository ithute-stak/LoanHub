"""Immutable maker-checker reversal decision evidence.

Revision ID: r8l1a2p5f475
Revises: r8l1c2m4f467
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r8l1a2p5f475"
down_revision = "r8l1c2m4f467"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loan_rollover_reversal_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_rollover_transfers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("maker_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("checker_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approval_reference", sa.String(180), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("transfer_id", name="uq_rollover_reversal_approval_transfer"),
        sa.UniqueConstraint("company_id", "approval_reference", name="uq_rollover_reversal_approval_ref"),
        sa.CheckConstraint("maker_user_id <> checker_user_id", name="ck_rollover_reversal_independent"),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_rollover_reversal_decision"),
    )
    op.create_index("ix_loan_rollover_reversal_approvals_company_id", "loan_rollover_reversal_approvals", ["company_id"])
    op.execute("""
        CREATE TRIGGER trg_rollover_reversal_approval_immutable
        BEFORE UPDATE OR DELETE ON loan_rollover_reversal_approvals
        FOR EACH ROW EXECUTE FUNCTION prevent_rollover_transfer_mutation()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_rollover_reversal_approval_immutable ON loan_rollover_reversal_approvals")
    op.drop_index("ix_loan_rollover_reversal_approvals_company_id", table_name="loan_rollover_reversal_approvals")
    op.drop_table("loan_rollover_reversal_approvals")
