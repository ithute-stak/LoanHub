"""add company SIP routing policy

Revision ID: c3s6t8u0v134
Revises: c2r6t8u0v133
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3s6t8u0v134"
down_revision: Union[str, Sequence[str], None] = "c2r6t8u0v133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "call_management_policies",
        sa.Column("sip_outbound_trunk_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "call_management_policies",
        sa.Column("sip_caller_number", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("call_management_policies", "sip_caller_number")
    op.drop_column("call_management_policies", "sip_outbound_trunk_id")
