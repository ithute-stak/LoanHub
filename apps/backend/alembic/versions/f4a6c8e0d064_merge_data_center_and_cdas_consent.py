"""Merge Data Center pilot audit and CDAS consent review migration heads.

Revision ID: f4a6c8e0d064
Revises: e3f5a7c9d063, dc20261122002

Pure graph merge; neither feature is activated by this revision.
"""
revision = "f4a6c8e0d064"
down_revision = ("e3f5a7c9d063", "dc20261122002")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
