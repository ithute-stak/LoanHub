"""document studio folders

Revision ID: d3s7u9w1x243
Revises: c2r6t8v0w132
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d3s7u9w1x243"
down_revision: Union[str, Sequence[str], None] = "c2r6t8v0w132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_document_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["workspace_document_folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_document_folders_owner_user_id", "workspace_document_folders", ["owner_user_id"], unique=False)
    op.create_index("ix_workspace_document_folders_company_id", "workspace_document_folders", ["company_id"], unique=False)
    op.create_index("ix_workspace_document_folders_parent_id", "workspace_document_folders", ["parent_id"], unique=False)
    op.create_index("ix_workspace_document_folders_is_deleted", "workspace_document_folders", ["is_deleted"], unique=False)
    op.create_index(
        "uq_workspace_document_folder_root_name",
        "workspace_document_folders",
        ["owner_user_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND is_deleted = false"),
    )
    op.create_index(
        "uq_workspace_document_folder_child_name",
        "workspace_document_folders",
        ["owner_user_id", "parent_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL AND is_deleted = false"),
    )

    op.create_table(
        "workspace_document_folder_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["workspace_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["workspace_document_folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_workspace_document_folder_item_document"),
    )
    op.create_index("ix_workspace_document_folder_items_folder_id", "workspace_document_folder_items", ["folder_id"], unique=False)
    op.create_index("ix_workspace_document_folder_items_document_id", "workspace_document_folder_items", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workspace_document_folder_items_document_id", table_name="workspace_document_folder_items")
    op.drop_index("ix_workspace_document_folder_items_folder_id", table_name="workspace_document_folder_items")
    op.drop_table("workspace_document_folder_items")
    op.drop_index("uq_workspace_document_folder_child_name", table_name="workspace_document_folders")
    op.drop_index("uq_workspace_document_folder_root_name", table_name="workspace_document_folders")
    op.drop_index("ix_workspace_document_folders_is_deleted", table_name="workspace_document_folders")
    op.drop_index("ix_workspace_document_folders_parent_id", table_name="workspace_document_folders")
    op.drop_index("ix_workspace_document_folders_company_id", table_name="workspace_document_folders")
    op.drop_index("ix_workspace_document_folders_owner_user_id", table_name="workspace_document_folders")
    op.drop_table("workspace_document_folders")
