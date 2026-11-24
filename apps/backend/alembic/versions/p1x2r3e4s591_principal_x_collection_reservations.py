"""Create durable Principal x collection reservations (disabled by default).

Revision ID: p1x2r3e4s591
Revises: p1x2m3o4d590

This migration creates no payments and does not enable live collections.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p1x2r3e4s591"
down_revision: Union[str, Sequence[str], None] = "p1x2m3o4d590"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "principal_x_collection_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("provider_reference", sa.String(180), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["loan_id", "company_id"],
            ["client_company_loan.id", "client_company_loan.company_id"],
            name="fk_principal_x_reservation_loan_owner", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"], ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_principal_x_reservation_idempotency"),
        sa.UniqueConstraint("provider_reference", name="uq_principal_x_reservation_provider_reference"),
        sa.UniqueConstraint("payment_transaction_id", name="uq_principal_x_reservation_payment"),
        sa.CheckConstraint("amount > 0", name="ck_principal_x_reservation_positive"),
        sa.CheckConstraint("length(trim(idempotency_key)) > 0", name="ck_principal_x_reservation_key_nonempty"),
        sa.CheckConstraint("length(trim(provider_reference)) > 0", name="ck_principal_x_reservation_provider_nonempty"),
    )
    op.create_index(
        "ix_principal_x_reservations_loan",
        "principal_x_collection_reservations", ["company_id", "loan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_principal_x_reservations_loan", table_name="principal_x_collection_reservations")
    op.drop_table("principal_x_collection_reservations")
