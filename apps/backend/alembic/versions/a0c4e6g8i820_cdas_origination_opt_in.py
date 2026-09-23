"""Add CDAS collection preference to direct loan applications.

Revision ID: a0c4e6g8i820
Revises: z9n3p5q7r800
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a0c4e6g8i820"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deliberately leave existing rows NULL.  NULL means the application/loan
    # predates per-loan CDAS consent and therefore remains under the legacy
    # stored-employee-number behaviour.  New ORM-created applications default
    # to False until the origination checkbox is explicitly enabled.
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_collection_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_employee_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_linked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column("cdas_linked_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_direct_loan_applications_cdas_linked_by_user_id_users",
        "direct_loan_applications",
        "users",
        ["cdas_linked_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_collection_enabled",
        "direct_loan_applications",
        ["cdas_collection_enabled"],
        unique=False,
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_employee_number",
        "direct_loan_applications",
        ["cdas_employee_number"],
        unique=False,
    )
    op.create_index(
        "ix_direct_loan_applications_cdas_linked_by_user_id",
        "direct_loan_applications",
        ["cdas_linked_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_direct_loan_applications_cdas_linked_by_user_id", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_cdas_employee_number", table_name="direct_loan_applications")
    op.drop_index("ix_direct_loan_applications_cdas_collection_enabled", table_name="direct_loan_applications")
    op.drop_constraint(
        "fk_direct_loan_applications_cdas_linked_by_user_id_users",
        "direct_loan_applications",
        type_="foreignkey",
    )
    op.drop_column("direct_loan_applications", "cdas_linked_by_user_id")
    op.drop_column("direct_loan_applications", "cdas_linked_at")
    op.drop_column("direct_loan_applications", "cdas_employee_number")
    op.drop_column("direct_loan_applications", "cdas_collection_enabled")
