"""Join Principal x collection reservations and CDAS affordability attempt heads.

Revision ID: d2e4f6a8b062
Revises: c1d3a5f7b061, p1x2r3e4s591

Both branches retain their own DDL; this merge performs no schema mutation.
It does not activate collections or bulk CDAS execution.
"""
revision = "d2e4f6a8b062"
down_revision = ("c1d3a5f7b061", "p1x2r3e4s591")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
