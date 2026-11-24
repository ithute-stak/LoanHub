"""Merge LoanHub's operational migrations and document issuance draft schema.

Revision ID: d6e7f8a9b013
Revises: a1r2i3d4e690, c5d6e7f8a912

This is a graph-only Alembic merge. Neither production schema nor a live
database is changed by committing this draft. Both parents must be applied
before Alembic considers this head complete.
"""
from __future__ import annotations

revision = "d6e7f8a9b013"
down_revision = ("a1r2i3d4e690", "c5d6e7f8a912")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
