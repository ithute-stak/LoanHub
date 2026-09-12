"""Add encrypted provider payload storage for existing bureau enquiries.

LoanHub already created `credit_bureau_enquiries` in revision r1c2d3e4f510.
Experian therefore extends that canonical bureau ledger rather than creating a
second competing enquiry table.

Revision ID: n4d8f0a2b014
Revises: k1a5c7d9f011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "n4d8f0a2b014"
down_revision = "k1a5c7d9f011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_bureau_provider_payloads",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("enquiry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), server_default="experian", nullable=False),
        sa.Column("raw_response_encrypted", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["enquiry_id"], ["credit_bureau_enquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enquiry_id", name="uq_credit_bureau_provider_payload_enquiry"),
    )
    op.create_index(
        "ix_credit_bureau_provider_payloads_enquiry_id",
        "credit_bureau_provider_payloads",
        ["enquiry_id"],
    )
    op.create_index(
        "ix_credit_bureau_provider_payloads_company_id",
        "credit_bureau_provider_payloads",
        ["company_id"],
    )
    op.create_index(
        "ix_credit_bureau_provider_payloads_provider",
        "credit_bureau_provider_payloads",
        ["provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_bureau_provider_payloads_provider", table_name="credit_bureau_provider_payloads")
    op.drop_index("ix_credit_bureau_provider_payloads_company_id", table_name="credit_bureau_provider_payloads")
    op.drop_index("ix_credit_bureau_provider_payloads_enquiry_id", table_name="credit_bureau_provider_payloads")
    op.drop_table("credit_bureau_provider_payloads")
