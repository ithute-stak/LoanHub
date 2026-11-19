"""Merge Principal x and draft tenant-document issuance migration branches.

Revision ID: a9b0c1d2e346
Revises: p1x2r3e4s591, f8a9b0c1d235

Graph-only merge. Does not alter schema or production data. Both independent
parent migrations must be applied before this revision can become current.
Official document issuance remains non-routed and disabled.
"""
revision = "a9b0c1d2e346"
down_revision = ("p1x2r3e4s591", "f8a9b0c1d235")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
