"""borrower service requests

Revision ID: e4t8v0x2y354
Revises: d3s7u9w1x243
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e4t8v0x2y354"
down_revision: Union[str, Sequence[str], None] = "d3s7u9w1x243"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "borrower_service_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="submitted", nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("requested_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("company_response", sa.Text(), nullable=True),
        sa.Column("responded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrower_service_requests_borrower_id", "borrower_service_requests", ["borrower_id"], unique=False)
    op.create_index("ix_borrower_service_requests_company_id", "borrower_service_requests", ["company_id"], unique=False)
    op.create_index("ix_borrower_service_requests_loan_id", "borrower_service_requests", ["loan_id"], unique=False)
    op.create_index("ix_borrower_service_requests_request_type", "borrower_service_requests", ["request_type"], unique=False)
    op.create_index("ix_borrower_service_requests_status", "borrower_service_requests", ["status"], unique=False)
    op.create_index("ix_borrower_service_requests_responded_by_user_id", "borrower_service_requests", ["responded_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_borrower_service_requests_responded_by_user_id", table_name="borrower_service_requests")
    op.drop_index("ix_borrower_service_requests_status", table_name="borrower_service_requests")
    op.drop_index("ix_borrower_service_requests_request_type", table_name="borrower_service_requests")
    op.drop_index("ix_borrower_service_requests_loan_id", table_name="borrower_service_requests")
    op.drop_index("ix_borrower_service_requests_company_id", table_name="borrower_service_requests")
    op.drop_index("ix_borrower_service_requests_borrower_id", table_name="borrower_service_requests")
    op.drop_table("borrower_service_requests")
