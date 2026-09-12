"""add collaborative workspace document studio

Revision ID: s2d4e6f8a130
Revises: r1c2d3e4f510
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s2d4e6f8a130"
down_revision: Union[str, Sequence[str], None] = "r1c2d3e4f510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    )


def upgrade() -> None:
    """Create the original Document Studio schema with a frozen definition.

    Historical migrations must not build tables from today's ORM metadata.
    The current WorkspaceDocument model contains relationships and columns that
    were introduced by later revisions; using it here made a clean database
    depend on tables that did not exist yet.
    """
    op.create_table(
        "workspace_documents",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_edited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("template_key", sa.String(length=60), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("page_size", sa.String(length=20), nullable=False),
        sa.Column("orientation", sa.String(length=20), nullable=False),
        sa.Column("margin_top_mm", sa.Integer(), nullable=False),
        sa.Column("margin_right_mm", sa.Integer(), nullable=False),
        sa.Column("margin_bottom_mm", sa.Integer(), nullable=False),
        sa.Column("margin_left_mm", sa.Integer(), nullable=False),
        sa.Column("include_brand_header", sa.Boolean(), nullable=False),
        sa.Column("include_footer", sa.Boolean(), nullable=False),
        sa.Column("is_confidential", sa.Boolean(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_edited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_documents_owner_user_id", "workspace_documents", ["owner_user_id"])
    op.create_index("ix_workspace_documents_company_id", "workspace_documents", ["company_id"])
    op.create_index("ix_workspace_documents_branch_id", "workspace_documents", ["branch_id"])
    op.create_index("ix_workspace_documents_reference", "workspace_documents", ["reference"], unique=True)
    op.create_index("ix_workspace_documents_visibility", "workspace_documents", ["visibility"])
    op.create_index("ix_workspace_documents_status", "workspace_documents", ["status"])
    op.create_index("ix_workspace_documents_is_deleted", "workspace_documents", ["is_deleted"])

    op.create_table(
        "workspace_document_collaborators",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("permission", sa.String(length=20), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["document_id"], ["workspace_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "user_id", name="uq_workspace_document_collaborator"),
    )
    op.create_index("ix_workspace_document_collaborators_document_id", "workspace_document_collaborators", ["document_id"])
    op.create_index("ix_workspace_document_collaborators_user_id", "workspace_document_collaborators", ["user_id"])

    op.create_table(
        "workspace_document_revisions",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["document_id"], ["workspace_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version", name="uq_workspace_document_revision_version"),
    )
    op.create_index("ix_workspace_document_revisions_document_id", "workspace_document_revisions", ["document_id"])


def downgrade() -> None:
    op.drop_table("workspace_document_revisions")
    op.drop_table("workspace_document_collaborators")
    op.drop_table("workspace_documents")
