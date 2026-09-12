"""add mobile realtime push devices

Revision ID: c4t7u9v1w245
Revises: c3s6t8u0v134
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c4t7u9v1w245"
down_revision: Union[str, Sequence[str], None] = "c3s6t8u0v134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_push_devices",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_uuid", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=24), nullable=False, server_default="android"),
        sa.Column("provider", sa.String(length=24), nullable=False, server_default="fcm"),
        sa.Column("push_token", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "device_uuid", name="uq_mobile_push_device_user_device"),
    )
    op.create_index("ix_mobile_push_devices_user_id", "mobile_push_devices", ["user_id"], unique=False)
    op.create_index("ix_mobile_push_devices_is_active", "mobile_push_devices", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mobile_push_devices_is_active", table_name="mobile_push_devices")
    op.drop_index("ix_mobile_push_devices_user_id", table_name="mobile_push_devices")
    op.drop_table("mobile_push_devices")
