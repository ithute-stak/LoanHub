"""Add canonical bank-deduction work groups for CIVIL, FORCE and S/E.

Revision ID: h5j9l1n3p570
Revises: h5j9l1n3p569
"""
from alembic import op
import sqlalchemy as sa

revision = "h5j9l1n3p570"
down_revision = "h5j9l1n3p569"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for code, name in (("CIVIL", "CIVIL"), ("FORCE", "FORCE"), ("SE", "S/E")):
        conn.execute(sa.text("""
            INSERT INTO employer_groups (id, code, name, is_active, created_at, updated_at)
            VALUES (:id, :code, :name, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (code) DO NOTHING
        """), {"id": __import__("uuid").uuid4(), "code": code, "name": name})


def downgrade():
    # Do not delete potentially referenced financial work-group records.
    pass
