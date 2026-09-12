"""add Word-style document defaults and signature-field support

Revision ID: t3e5f7a9b240
Revises: s2d4e6f8a130
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t3e5f7a9b240"
down_revision: Union[str, Sequence[str], None] = "s2d4e6f8a130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "workspace_documents" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("workspace_documents")}


def upgrade() -> None:
    columns = _column_names()
    additions = (
        ("style_key", sa.Column("style_key", sa.String(length=40), nullable=False, server_default="modern_blue")),
        ("default_font_family", sa.Column("default_font_family", sa.String(length=80), nullable=False, server_default="Arial")),
        ("default_font_size_pt", sa.Column("default_font_size_pt", sa.Integer(), nullable=False, server_default="11")),
        ("default_line_height_percent", sa.Column("default_line_height_percent", sa.Integer(), nullable=False, server_default="115")),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("workspace_documents", column)


def downgrade() -> None:
    columns = _column_names()
    for name in (
        "default_line_height_percent",
        "default_font_size_pt",
        "default_font_family",
        "style_key",
    ):
        if name in columns:
            op.drop_column("workspace_documents", name)
