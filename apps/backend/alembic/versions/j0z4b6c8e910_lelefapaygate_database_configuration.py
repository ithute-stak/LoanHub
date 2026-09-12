"""Store LelefaPayGate platform configuration in the database.

Revision ID: j0z4b6c8e910
Revises: i9y3a5b7d809
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "j0z4b6c8e910"
down_revision = "i9y3a5b7d809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lelefapaygate_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=32), server_default="platform", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "base_url",
            sa.String(length=500),
            server_default="http://169.255.58.185:8081/api/v1",
            nullable=False,
        ),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("api_key_nonce", sa.String(length=80), nullable=True),
        sa.Column("api_key_encryption_version", sa.String(length=30), nullable=True),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=True),
        sa.Column("webhook_secret_nonce", sa.String(length=80), nullable=True),
        sa.Column("webhook_secret_encryption_version", sa.String(length=30), nullable=True),
        sa.Column("request_signing_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), server_default="15", nullable=False),
        sa.Column("webhook_tolerance_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("collection_provider", sa.String(length=50), server_default="mpesa", nullable=False),
        sa.Column("payout_provider", sa.String(length=50), server_default="mpesa", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", name="uq_lelefapaygate_configurations_scope"),
    )
    op.create_index(
        "ix_lelefapaygate_configurations_scope",
        "lelefapaygate_configurations",
        ["scope"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lelefapaygate_configurations_scope",
        table_name="lelefapaygate_configurations",
    )
    op.drop_table("lelefapaygate_configurations")
