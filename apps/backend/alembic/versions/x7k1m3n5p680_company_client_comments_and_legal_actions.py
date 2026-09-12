"""company client comments and legal actions

Revision ID: x7k1m3n5p680
Revises: w6h8j0k2m470, f1a9c4e7b620
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "x7k1m3n5p680"
down_revision: Union[str, Sequence[str], None] = ("w6h8j0k2m470", "f1a9c4e7b620")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_client_case_entries",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_borrower_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_type", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="general"),
        sa.Column("title", sa.String(length=180), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="recorded"),
        sa.Column("action_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_number", sa.String(length=180), nullable=True),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="LSL"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_borrower_account_id"], ["company_borrower_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_client_case_entries_company_id", "company_client_case_entries", ["company_id"], unique=False)
    op.create_index("ix_company_client_case_entries_branch_id", "company_client_case_entries", ["branch_id"], unique=False)
    op.create_index("ix_company_client_case_entries_company_borrower_account_id", "company_client_case_entries", ["company_borrower_account_id"], unique=False)
    op.create_index("ix_company_client_case_entries_borrower_id", "company_client_case_entries", ["borrower_id"], unique=False)
    op.create_index("ix_company_client_case_entries_created_by_user_id", "company_client_case_entries", ["created_by_user_id"], unique=False)
    op.create_index("ix_company_client_case_entries_entry_type", "company_client_case_entries", ["entry_type"], unique=False)
    op.create_index("ix_company_client_case_entries_category", "company_client_case_entries", ["category"], unique=False)
    op.create_index("ix_company_client_case_entries_status", "company_client_case_entries", ["status"], unique=False)
    op.create_index("ix_company_client_case_entries_action_date", "company_client_case_entries", ["action_date"], unique=False)
    op.create_index(
        "ix_company_client_case_entries_company_account_created",
        "company_client_case_entries",
        ["company_id", "company_borrower_account_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_company_client_case_entries_company_type_status",
        "company_client_case_entries",
        ["company_id", "entry_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_company_client_case_entries_company_type_status", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_company_account_created", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_action_date", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_status", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_category", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_entry_type", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_created_by_user_id", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_borrower_id", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_company_borrower_account_id", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_branch_id", table_name="company_client_case_entries")
    op.drop_index("ix_company_client_case_entries_company_id", table_name="company_client_case_entries")
    op.drop_table("company_client_case_entries")
