"""Complete CDAS billing with invoices and due terms.

Revision ID: c0e4g6h8j012
Revises: b9d3f5g7h911
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c0e4g6h8j012"
down_revision = "b9d3f5g7h911"
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
    op.add_column(
        "platform_cdas_subscriptions",
        sa.Column("billing_due_days", sa.Integer(), nullable=False, server_default="14"),
    )
    op.create_table(
        "platform_cdas_invoices",
        *_audit_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("waived_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount_due", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["platform_cdas_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "period_start", "period_end", name="uq_platform_cdas_invoice_period"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_platform_cdas_invoices_company_id", "platform_cdas_invoices", ["company_id"])
    op.create_index("ix_platform_cdas_invoices_subscription_id", "platform_cdas_invoices", ["subscription_id"])
    op.create_index("ix_platform_cdas_invoices_invoice_number", "platform_cdas_invoices", ["invoice_number"], unique=True)
    op.create_index("ix_platform_cdas_invoices_period_start", "platform_cdas_invoices", ["period_start"])
    op.create_index("ix_platform_cdas_invoices_period_end", "platform_cdas_invoices", ["period_end"])
    op.create_index("ix_platform_cdas_invoices_status", "platform_cdas_invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_platform_cdas_invoices_status", table_name="platform_cdas_invoices")
    op.drop_index("ix_platform_cdas_invoices_period_end", table_name="platform_cdas_invoices")
    op.drop_index("ix_platform_cdas_invoices_period_start", table_name="platform_cdas_invoices")
    op.drop_index("ix_platform_cdas_invoices_invoice_number", table_name="platform_cdas_invoices")
    op.drop_index("ix_platform_cdas_invoices_subscription_id", table_name="platform_cdas_invoices")
    op.drop_index("ix_platform_cdas_invoices_company_id", table_name="platform_cdas_invoices")
    op.drop_table("platform_cdas_invoices")
    op.drop_column("platform_cdas_subscriptions", "billing_due_days")
