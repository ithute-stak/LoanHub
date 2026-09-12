"""LelefaPayGate payment boundary and webhook inbox

Revision ID: d3s7u9w1x244
Revises: c2r6t8u0v132
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3s7u9w1x244"
down_revision: Union[str, Sequence[str], None] = "c2r6t8u0v132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymentprovider ADD VALUE IF NOT EXISTS 'LELEFAPAYGATE'")
    op.create_table(
        "lelefapaygate_webhook_events",
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_status", sa.String(length=24), server_default="received", nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_lpg_webhook_event_id", "lelefapaygate_webhook_events", ["event_id"], unique=True)
    op.create_index("ix_lpg_webhook_event_type", "lelefapaygate_webhook_events", ["event_type"], unique=False)
    op.create_index("ix_lpg_webhook_payment", "lelefapaygate_webhook_events", ["payment_id"], unique=False)
    op.create_index("ix_lpg_webhook_status", "lelefapaygate_webhook_events", ["processing_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lpg_webhook_status", table_name="lelefapaygate_webhook_events")
    op.drop_index("ix_lpg_webhook_payment", table_name="lelefapaygate_webhook_events")
    op.drop_index("ix_lpg_webhook_event_type", table_name="lelefapaygate_webhook_events")
    op.drop_index("ix_lpg_webhook_event_id", table_name="lelefapaygate_webhook_events")
    op.drop_table("lelefapaygate_webhook_events")
    # PostgreSQL enum labels are intentionally retained on downgrade because
    # removing one requires rewriting every dependent column.
