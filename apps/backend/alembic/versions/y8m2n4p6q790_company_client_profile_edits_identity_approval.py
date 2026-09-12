"""company client profile edits and dual national id approval

Revision ID: y8m2n4p6q790
Revises: x7k1m3n5p680
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "y8m2n4p6q790"
down_revision: Union[str, Sequence[str], None] = "x7k1m3n5p680"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_client_identity_change_requests",
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_borrower_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_national_id", sa.String(length=50), nullable=True),
        sa.Column("proposed_national_id", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("borrower_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("borrower_approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_owner_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_owner_approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_by_role", sa.String(length=40), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["applied_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_borrower_account_id"], ["company_borrower_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_owner_approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_company_client_identity_change_requests_reference", "company_client_identity_change_requests", ["reference"], unique=True)
    op.create_index("ix_company_client_identity_change_requests_company_id", "company_client_identity_change_requests", ["company_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_branch_id", "company_client_identity_change_requests", ["branch_id"], unique=False)
    op.create_index("ix_cc_identity_change_account_id", "company_client_identity_change_requests", ["company_borrower_account_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_borrower_id", "company_client_identity_change_requests", ["borrower_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_person_id", "company_client_identity_change_requests", ["person_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_requested_by_user_id", "company_client_identity_change_requests", ["requested_by_user_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_proposed_national_id", "company_client_identity_change_requests", ["proposed_national_id"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_status", "company_client_identity_change_requests", ["status"], unique=False)
    op.create_index("ix_company_client_identity_change_requests_expires_at", "company_client_identity_change_requests", ["expires_at"], unique=False)
    op.create_index(
        "uq_company_client_identity_change_pending_account",
        "company_client_identity_change_requests",
        ["company_borrower_account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_company_client_identity_change_company_status_created",
        "company_client_identity_change_requests",
        ["company_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_company_client_identity_change_company_status_created", table_name="company_client_identity_change_requests")
    op.drop_index("uq_company_client_identity_change_pending_account", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_expires_at", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_status", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_proposed_national_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_requested_by_user_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_person_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_borrower_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_cc_identity_change_account_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_branch_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_company_id", table_name="company_client_identity_change_requests")
    op.drop_index("ix_company_client_identity_change_requests_reference", table_name="company_client_identity_change_requests")
    op.drop_table("company_client_identity_change_requests")
