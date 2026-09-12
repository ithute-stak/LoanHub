"""company operating system

Revision ID: f5u9w1y3z465
Revises: e4t8v0x2y354
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f5u9w1y3z465"
down_revision: Union[str, Sequence[str], None] = "e4t8v0x2y354"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_operating_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("module", sa.String(length=60), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=30), nullable=False, server_default="normal"),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("counterparty_name", sa.String(length=240), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference", name="uq_company_operating_record_reference"),
    )
    for column in ("company_id", "branch_id", "module", "record_type", "reference", "status", "priority", "borrower_id", "loan_id", "assigned_user_id", "counterparty_name", "due_at", "is_archived"):
        op.create_index(f"ix_company_operating_records_{column}", "company_operating_records", [column], unique=False)

    op.create_table(
        "company_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("allowed_ips", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_prefix", name="uq_company_api_key_prefix"),
    )
    op.create_index("ix_company_api_keys_company_id", "company_api_keys", ["company_id"], unique=False)
    op.create_index("ix_company_api_keys_key_prefix", "company_api_keys", ["key_prefix"], unique=False)
    op.create_index("ix_company_api_keys_revoked_at", "company_api_keys", ["revoked_at"], unique=False)

    op.create_table(
        "company_webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("endpoint_url", sa.String(length=500), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("secret_prefix", sa.String(length=24), nullable=False),
        sa.Column("event_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_delivery_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_webhook_endpoints_company_id", "company_webhook_endpoints", ["company_id"], unique=False)
    op.create_index("ix_company_webhook_endpoints_is_active", "company_webhook_endpoints", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_company_webhook_endpoints_is_active", table_name="company_webhook_endpoints")
    op.drop_index("ix_company_webhook_endpoints_company_id", table_name="company_webhook_endpoints")
    op.drop_table("company_webhook_endpoints")
    op.drop_index("ix_company_api_keys_revoked_at", table_name="company_api_keys")
    op.drop_index("ix_company_api_keys_key_prefix", table_name="company_api_keys")
    op.drop_index("ix_company_api_keys_company_id", table_name="company_api_keys")
    op.drop_table("company_api_keys")
    for column in reversed(("company_id", "branch_id", "module", "record_type", "reference", "status", "priority", "borrower_id", "loan_id", "assigned_user_id", "counterparty_name", "due_at", "is_archived")):
        op.drop_index(f"ix_company_operating_records_{column}", table_name="company_operating_records")
    op.drop_table("company_operating_records")
