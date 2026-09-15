"""Link CDAS opportunities to LoanHub origination drafts.

Revision ID: g7v1w3x5y030
Revises: f6u0v2w4x029
Create Date: 2026-09-15

Adds provenance only. CDAS data does not populate affordability, pricing,
approval, eligibility or disbursement fields.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g7v1w3x5y030"
down_revision = "f6u0v2w4x029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_source_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_source_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_handoff_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_handoff_at", sa.DateTime(), nullable=True),
    )

    op.create_foreign_key(
        "fk_direct_loan_applications_cdas_source_opportunity",
        "direct_loan_applications",
        "cdas_booking_opportunities",
        ["cdas_source_opportunity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_direct_loan_applications_cdas_source_analysis",
        "direct_loan_applications",
        "cdas_analysis_records",
        ["cdas_source_analysis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_direct_loan_applications_cdas_handoff_user",
        "direct_loan_applications",
        "users",
        ["cdas_handoff_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "uq_direct_loan_applications_cdas_source_opportunity",
        "direct_loan_applications",
        ["cdas_source_opportunity_id"],
        unique=True,
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_source_analysis_id",
        "direct_loan_applications",
        ["cdas_source_analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_handoff_by_user_id",
        "direct_loan_applications",
        ["cdas_handoff_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_handoff_at",
        "direct_loan_applications",
        ["cdas_handoff_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_direct_loan_applications_cdas_handoff_at", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_cdas_handoff_by_user_id", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_cdas_source_analysis_id", table_name="direct_loan_applications")
    op.drop_index("uq_direct_loan_applications_cdas_source_opportunity", table_name="direct_loan_applications")
    op.drop_constraint(
        "fk_direct_loan_applications_cdas_handoff_user",
        "direct_loan_applications",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_direct_loan_applications_cdas_source_analysis",
        "direct_loan_applications",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_direct_loan_applications_cdas_source_opportunity",
        "direct_loan_applications",
        type_="foreignkey",
    )
    op.drop_column("direct_loan_applications", "cdas_handoff_at")
    op.drop_column("direct_loan_applications", "cdas_handoff_by_user_id")
    op.drop_column("direct_loan_applications", "cdas_source_analysis_id")
    op.drop_column("direct_loan_applications", "cdas_source_opportunity_id")
