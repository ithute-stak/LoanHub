"""add internal/external file sharing settings

Revision ID: p8a4d6e2f910
Revises: m5d7c9e2a140
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p8a4d6e2f910"
down_revision: Union[str, Sequence[str], None] = "m5d7c9e2a140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_social_share_settings",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_sharing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_expiry_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("default_message", sa.Text(), nullable=True),
        sa.Column(
            "enabled_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"native\", \"whatsapp\", \"email\"]'::jsonb"),
        ),
        sa.Column("whatsapp_number", sa.String(length=40), nullable=True),
        sa.Column("facebook_url", sa.String(length=500), nullable=True),
        sa.Column("instagram_url", sa.String(length=500), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("x_handle", sa.String(length=100), nullable=True),
        sa.Column("telegram_username", sa.String(length=100), nullable=True),
        sa.Column("youtube_url", sa.String(length=500), nullable=True),
        sa.Column("configured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_company_social_share_settings_company"),
    )
    op.create_index("ix_company_social_share_settings_company_id", "company_social_share_settings", ["company_id"], unique=False)

    op.create_table(
        "external_file_shares",
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allow_download", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["managed_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_file_shares_company_id", "external_file_shares", ["company_id"], unique=False)
    op.create_index("ix_external_file_shares_created_by_user_id", "external_file_shares", ["created_by_user_id"], unique=False)
    op.create_index("ix_external_file_shares_expires_at", "external_file_shares", ["expires_at"], unique=False)
    op.create_index("ix_external_file_shares_file_id", "external_file_shares", ["file_id"], unique=False)
    op.create_index("ix_external_file_shares_revoked_at", "external_file_shares", ["revoked_at"], unique=False)
    op.create_index("ix_external_file_shares_token_hash", "external_file_shares", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_external_file_shares_token_hash", table_name="external_file_shares")
    op.drop_index("ix_external_file_shares_revoked_at", table_name="external_file_shares")
    op.drop_index("ix_external_file_shares_file_id", table_name="external_file_shares")
    op.drop_index("ix_external_file_shares_expires_at", table_name="external_file_shares")
    op.drop_index("ix_external_file_shares_created_by_user_id", table_name="external_file_shares")
    op.drop_index("ix_external_file_shares_company_id", table_name="external_file_shares")
    op.drop_table("external_file_shares")
    op.drop_index("ix_company_social_share_settings_company_id", table_name="company_social_share_settings")
    op.drop_table("company_social_share_settings")
