"""Bind execution permits to exact source-PDF signature-field coordinates.

Revision ID: c8d9e0f1a390
Revises: b7c8d9e0f289
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a390"
down_revision = "b7c8d9e0f289"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy unbound permits remain NULL and must fail closed.
    for column in ("field_page_index", "field_page_count"):
        op.add_column("wacom_execution_authorizations", sa.Column(column, sa.Integer()))
    for column in ("field_x", "field_y", "field_width", "field_height"):
        op.add_column("wacom_execution_authorizations", sa.Column(column, sa.Numeric(10, 3)))
    op.add_column("wacom_execution_authorizations", sa.Column("field_binding_sha256", sa.String(64)))
    op.create_check_constraint(
        "ck_wacom_execution_field_complete",
        "wacom_execution_authorizations",
        "(field_binding_sha256 IS NULL AND field_page_index IS NULL "
        "AND field_page_count IS NULL AND field_x IS NULL AND field_y IS NULL "
        "AND field_width IS NULL AND field_height IS NULL) OR "
        "(length(field_binding_sha256) = 64 AND field_page_index >= 0 "
        "AND field_page_count > field_page_index AND field_page_count <= 100 "
        "AND field_width > 0 AND field_height > 0 AND field_x >= 0 AND field_y >= 0)",
    )


def downgrade():
    op.drop_constraint("ck_wacom_execution_field_complete", "wacom_execution_authorizations", type_="check")
    for column in ("field_binding_sha256", "field_height", "field_width", "field_y", "field_x", "field_page_count", "field_page_index"):
        op.drop_column("wacom_execution_authorizations", column)
