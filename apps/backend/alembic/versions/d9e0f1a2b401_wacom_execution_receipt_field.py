"""Bind each execution reservation to an independently approved PDF field.

Revision ID: d9e0f1a2b401
Revises: c8d9e0f1a390
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b401"
down_revision = "c8d9e0f1a390"
branch_labels = None
depends_on = None


def upgrade():
    # Historical receipts are not safe to infer field placement for.
    # An existing unbound receipt blocks migration until reviewed.
    connection = op.get_bind()
    count = connection.execute(
        sa.text("SELECT count(*) FROM wacom_execution_receipts")
    ).scalar_one()
    if count:
        raise RuntimeError(
            "Wacom execution receipts exist without field hashes; "
            "migrate records using a separately reviewed recovery procedure"
        )
    op.add_column(
        "wacom_execution_receipts",
        sa.Column("field_binding_sha256", sa.String(64), nullable=False),
    )
    op.create_check_constraint(
        "ck_wacom_receipt_field_hash_length",
        "wacom_execution_receipts",
        "length(field_binding_sha256) = 64",
    )


def downgrade():
    op.drop_constraint(
        "ck_wacom_receipt_field_hash_length",
        "wacom_execution_receipts", type_="check",
    )
    op.drop_column("wacom_execution_receipts", "field_binding_sha256")
