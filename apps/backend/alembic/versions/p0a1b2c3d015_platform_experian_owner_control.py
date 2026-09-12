"""Add platform-owner credit bureau configuration.

Revision ID: p0a1b2c3d015
Revises: n4d8f0a2b014
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "p0a1b2c3d015"
down_revision = "n4d8f0a2b014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_credit_bureau_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=30), server_default="sandbox", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("last_test_status", sa.String(length=100), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", name="uq_platform_credit_bureau_provider"),
    )
    op.create_index(
        "ix_platform_credit_bureau_configurations_provider",
        "platform_credit_bureau_configurations",
        ["provider"],
    )
    op.create_index(
        "ix_platform_credit_bureau_configurations_configured_by_user_id",
        "platform_credit_bureau_configurations",
        ["configured_by_user_id"],
    )

    # Experian credentials and provider API mapping are no longer company-owned.
    # Retain only company policy keys in tenant rows; the Platform Owner must
    # deliberately configure the single central credential/API contract after
    # this migration.
    op.execute(
        sa.text(
            """
            UPDATE origination_integration_configurations
               SET encrypted_credentials = NULL,
                   environment = 'platform',
                   last_test_status = NULL,
                   last_tested_at = NULL,
                   configuration = COALESCE(configuration, '{}'::jsonb)
                       - 'region'
                       - 'product'
                       - 'bureau_endpoint_path'
                       - 'request_template'
                       - 'response_mapping'
             WHERE provider = 'experian'
            """
        )
    )


def downgrade() -> None:
    # Retired company Experian secrets/provider mapping are intentionally not restored.
    op.drop_index(
        "ix_platform_credit_bureau_configurations_configured_by_user_id",
        table_name="platform_credit_bureau_configurations",
    )
    op.drop_index(
        "ix_platform_credit_bureau_configurations_provider",
        table_name="platform_credit_bureau_configurations",
    )
    op.drop_table("platform_credit_bureau_configurations")
