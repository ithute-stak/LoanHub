"""Merge legacy cashbook and Experian platform migration heads.

Revision ID: q1c4e7g0h016
Revises: p0a1b2c3d015, m3c7e9f1a013
Create Date: 2026-08-17

This merge revision reconciles two legitimate migration histories that diverged
at k1a5c7d9e011. Databases that already applied the legacy cashbook branch can
safely receive the Experian branch, while databases on current main can receive
the historical legacy migrations without stamping or rewriting alembic_version.
"""


revision = "q1c4e7g0h016"
down_revision = ("p0a1b2c3d015", "m3c7e9f1a013")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
