"""document branding, reusable signatures, cover pages and positioned addresses

Revision ID: v5g7c9d2e460
Revises: u4f6a8b1c350
Create Date: 2026-07-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v5g7c9d2e460"
down_revision = "u4f6a8b1c350"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_document_assets",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=False, server_default="image/png"),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encryption_nonce", sa.String(length=255), nullable=True),
        sa.Column("encryption_version", sa.String(length=20), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("processing_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_document_assets_owner_user_id", "workspace_document_assets", ["owner_user_id"])
    op.create_index("ix_workspace_document_assets_company_id", "workspace_document_assets", ["company_id"])
    op.create_index("ix_workspace_document_assets_kind", "workspace_document_assets", ["kind"])
    op.create_index("ix_workspace_document_assets_sha256", "workspace_document_assets", ["sha256"])
    op.create_index("ix_workspace_document_assets_is_default", "workspace_document_assets", ["is_default"])
    op.create_index("ix_workspace_document_assets_is_active", "workspace_document_assets", ["is_active"])

    op.add_column("workspace_documents", sa.Column("brand_logo_asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("workspace_documents", sa.Column("cover_page_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("workspace_documents", sa.Column("cover_page", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("workspace_documents", sa.Column("address_blocks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.create_foreign_key(
        "fk_workspace_documents_brand_logo_asset",
        "workspace_documents",
        "workspace_document_assets",
        ["brand_logo_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_workspace_documents_brand_logo_asset_id", "workspace_documents", ["brand_logo_asset_id"])

    op.create_table(
        "workspace_document_signatures",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", sa.String(length=80), nullable=False),
        sa.Column("field_type", sa.String(length=30), nullable=False, server_default="signature"),
        sa.Column("signer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signer_name", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("verification_code", sa.String(length=32), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["workspace_document_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["workspace_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["signer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_code"),
    )
    op.create_index("ix_workspace_document_signatures_document_id", "workspace_document_signatures", ["document_id"])
    op.create_index("ix_workspace_document_signatures_field_id", "workspace_document_signatures", ["field_id"])
    op.create_index("ix_workspace_document_signatures_signer_user_id", "workspace_document_signatures", ["signer_user_id"])
    op.create_index("ix_workspace_document_signatures_document_hash", "workspace_document_signatures", ["document_hash"])
    op.create_index("ix_workspace_document_signatures_verification_code", "workspace_document_signatures", ["verification_code"], unique=True)
    op.create_index("ix_workspace_document_signatures_revoked_at", "workspace_document_signatures", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_workspace_document_signatures_revoked_at", table_name="workspace_document_signatures")
    op.drop_index("ix_workspace_document_signatures_verification_code", table_name="workspace_document_signatures")
    op.drop_index("ix_workspace_document_signatures_document_hash", table_name="workspace_document_signatures")
    op.drop_index("ix_workspace_document_signatures_signer_user_id", table_name="workspace_document_signatures")
    op.drop_index("ix_workspace_document_signatures_field_id", table_name="workspace_document_signatures")
    op.drop_index("ix_workspace_document_signatures_document_id", table_name="workspace_document_signatures")
    op.drop_table("workspace_document_signatures")

    op.drop_index("ix_workspace_documents_brand_logo_asset_id", table_name="workspace_documents")
    op.drop_constraint("fk_workspace_documents_brand_logo_asset", "workspace_documents", type_="foreignkey")
    op.drop_column("workspace_documents", "address_blocks")
    op.drop_column("workspace_documents", "cover_page")
    op.drop_column("workspace_documents", "cover_page_enabled")
    op.drop_column("workspace_documents", "brand_logo_asset_id")

    op.drop_index("ix_workspace_document_assets_is_active", table_name="workspace_document_assets")
    op.drop_index("ix_workspace_document_assets_is_default", table_name="workspace_document_assets")
    op.drop_index("ix_workspace_document_assets_sha256", table_name="workspace_document_assets")
    op.drop_index("ix_workspace_document_assets_kind", table_name="workspace_document_assets")
    op.drop_index("ix_workspace_document_assets_company_id", table_name="workspace_document_assets")
    op.drop_index("ix_workspace_document_assets_owner_user_id", table_name="workspace_document_assets")
    op.drop_table("workspace_document_assets")
