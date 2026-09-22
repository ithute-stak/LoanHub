"""Official CDAS mandate lifecycle

Revision ID: c6u0v2w4x247
Revises: z9n3p5q7r800
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c6u0v2w4x247"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "cdas_official_mandate_states",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mandate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("deduction_id", sa.Integer(), nullable=True),
        sa.Column("item_code", sa.String(length=100), nullable=False),
        sa.Column("reference_no", sa.String(length=200), nullable=False),
        sa.Column("loan_policy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("principal_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("effective_month", sa.String(length=32), nullable=False),
        sa.Column("cdas_status", sa.Integer(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=60), nullable=False, server_default="registration_pending"),
        sa.Column("last_request_type", sa.Integer(), nullable=True),
        sa.Column("requires_reconciliation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_provider_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mandate_id"], ["cdas_deduction_mandates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["direct_loan_applications.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("mandate_id", name="uq_cdas_official_state_mandate"),
        sa.UniqueConstraint("company_id", "environment", "reference_no", name="uq_cdas_official_state_reference"),
        sa.UniqueConstraint("company_id", "environment", "deduction_id", name="uq_cdas_official_state_deduction_id"),
    )
    op.create_index("ix_cdas_official_mandate_states_company_id", "cdas_official_mandate_states", ["company_id"])
    op.create_index("ix_cdas_official_mandate_states_mandate_id", "cdas_official_mandate_states", ["mandate_id"])
    op.create_index("ix_cdas_official_mandate_states_application_id", "cdas_official_mandate_states", ["application_id"])
    op.create_index("ix_cdas_official_mandate_states_environment", "cdas_official_mandate_states", ["environment"])
    op.create_index("ix_cdas_official_mandate_states_deduction_id", "cdas_official_mandate_states", ["deduction_id"])
    op.create_index("ix_cdas_official_mandate_states_reference_no", "cdas_official_mandate_states", ["reference_no"])
    op.create_index("ix_cdas_official_mandate_states_cdas_status", "cdas_official_mandate_states", ["cdas_status"])
    op.create_index("ix_cdas_official_mandate_states_lifecycle_status", "cdas_official_mandate_states", ["lifecycle_status"])
    op.create_index("ix_cdas_official_mandate_states_requires_reconciliation", "cdas_official_mandate_states", ["requires_reconciliation"])

    op.create_table(
        "cdas_official_mandate_events",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("request_type", sa.Integer(), nullable=True),
        sa.Column("request_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["state_id"], ["cdas_official_mandate_states.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_cdas_official_mandate_events_company_id", "cdas_official_mandate_events", ["company_id"])
    op.create_index("ix_cdas_official_mandate_events_state_id", "cdas_official_mandate_events", ["state_id"])
    op.create_index("ix_cdas_official_mandate_events_actor_user_id", "cdas_official_mandate_events", ["actor_user_id"])
    op.create_index("ix_cdas_official_mandate_events_event_type", "cdas_official_mandate_events", ["event_type"])
    op.create_index("ix_cdas_official_mandate_events_success", "cdas_official_mandate_events", ["success"])


def downgrade() -> None:
    op.drop_table("cdas_official_mandate_events")
    op.drop_table("cdas_official_mandate_states")
