"""Bind consent evidence to a real LoanHub managed file.

Revision ID: f5b7d9a1e065
Revises: f4a6c8e0d064

Nullable for historical pending records. Live CDAS consent checks reject NULL.
No record is approved and no provider execution is enabled by this migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f5b7d9a1e065"
down_revision = "f4a6c8e0d064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cdas_affordability_consent_evidence",
        sa.Column("managed_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cdas_consent_managed_file",
        "cdas_affordability_consent_evidence",
        "managed_files",
        ["managed_file_id"], ["id"], ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cdas_consent_managed_file",
        "cdas_affordability_consent_evidence",
        type_="foreignkey",
    )
    op.drop_column("cdas_affordability_consent_evidence", "managed_file_id")
