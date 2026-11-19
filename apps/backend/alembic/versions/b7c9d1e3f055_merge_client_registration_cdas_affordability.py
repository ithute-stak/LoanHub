"""Merge client-registration and CDAS affordability draft migration heads.

Revision ID: b7c9d1e3f055
Revises: a1r2i3d4e690, a9c4e7b2d851

This migration only joins two independent schema branches.
It does not change existing loan, client, or payroll data.
"""
revision = "b7c9d1e3f055"
down_revision = ("a1r2i3d4e690", "a9c4e7b2d851")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
