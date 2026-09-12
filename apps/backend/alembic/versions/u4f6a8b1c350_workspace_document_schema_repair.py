"""repair and verify the Document Studio database schema

Revision ID: u4f6a8b1c350
Revises: t3e5f7a9b240
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from database.base import Base
from database.models import workspace_document  # noqa: F401

revision: str = "u4f6a8b1c350"
down_revision: Union[str, Sequence[str], None] = "t3e5f7a9b240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "workspace_documents",
    "workspace_document_collaborators",
    "workspace_document_revisions",
)

_STYLE_COLUMNS = (
    (
        "style_key",
        sa.Column(
            "style_key",
            sa.String(length=40),
            nullable=False,
            server_default="modern_blue",
        ),
    ),
    (
        "default_font_family",
        sa.Column(
            "default_font_family",
            sa.String(length=80),
            nullable=False,
            server_default="Arial",
        ),
    ),
    (
        "default_font_size_pt",
        sa.Column(
            "default_font_size_pt",
            sa.Integer(),
            nullable=False,
            server_default="11",
        ),
    ),
    (
        "default_line_height_percent",
        sa.Column(
            "default_line_height_percent",
            sa.Integer(),
            nullable=False,
            server_default="115",
        ),
    ),
)


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {
        column["name"]
        for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()

    # The earlier release used check-first table creation. Repeating it here is
    # deliberate: it repairs installations where a manual/stamped migration or
    # interrupted deployment left one of the three workspace tables absent.
    for table_name in _TABLES:
        Base.metadata.tables[table_name].create(
            bind=bind,
            checkfirst=True,
        )

    existing = _columns("workspace_documents")
    for name, column in _STYLE_COLUMNS:
        if name not in existing:
            op.add_column("workspace_documents", column)


def downgrade() -> None:
    # This is a repair migration. Dropping repaired tables or columns could
    # destroy documents, so rollback intentionally leaves data structures in
    # place. The preceding feature migration remains responsible for a full
    # feature downgrade when that is explicitly required.
    pass
