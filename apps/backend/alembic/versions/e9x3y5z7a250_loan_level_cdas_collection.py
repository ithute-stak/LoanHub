"""Persist CDAS collection choice on applications and loans.

Revision ID: e9x3y5z7a250
Revises: e8w2x4y6z249
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e9x3y5z7a250"
down_revision: Union[str, Sequence[str], None] = "e8w2x4y6z249"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPLICATION_INDEX = "ix_direct_loan_applications_cdas_collection_enabled"
LOAN_INDEX = "ix_client_company_loan_cdas_collection_enabled"


def upgrade() -> None:
    op.add_column(
        "direct_loan_applications",
        sa.Column(
            "cdas_collection_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "direct_loan_applications",
        sa.Column(
            "cdas_collection_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        APPLICATION_INDEX,
        "direct_loan_applications",
        ["cdas_collection_enabled"],
        unique=False,
    )

    op.add_column(
        "client_company_loan",
        sa.Column(
            "cdas_collection_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "client_company_loan",
        sa.Column(
            "cdas_collection_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        LOAN_INDEX,
        "client_company_loan",
        ["cdas_collection_enabled"],
        unique=False,
    )

    # Existing CDAS mandates are already explicit collection instructions. Keep
    # those loans enabled when introducing the safer opt-in default so a
    # deployment does not silently stop lifecycle management for live mandates.
    op.execute(
        sa.text(
            """
            UPDATE client_company_loan AS loan
            SET cdas_collection_enabled = TRUE,
                cdas_collection_plan = jsonb_build_object(
                    'method', 'cdas_payroll',
                    'mode', 'automatic_monthly_payroll',
                    'authorization_basis', 'EXISTING_CDAS_MANDATE_BACKFILL',
                    'source', 'migration_e9x3y5z7a250'
                )
            WHERE EXISTS (
                SELECT 1
                FROM cdas_deduction_mandates AS mandate
                WHERE mandate.loan_id = loan.id
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE direct_loan_applications AS application
            SET cdas_collection_enabled = TRUE,
                cdas_collection_plan = loan.cdas_collection_plan
            FROM client_company_loan AS loan
            WHERE application.loan_id = loan.id
              AND loan.cdas_collection_enabled = TRUE
            """
        )
    )


def downgrade() -> None:
    op.drop_index(LOAN_INDEX, table_name="client_company_loan")
    op.drop_column("client_company_loan", "cdas_collection_plan")
    op.drop_column("client_company_loan", "cdas_collection_enabled")

    op.drop_index(APPLICATION_INDEX, table_name="direct_loan_applications")
    op.drop_column("direct_loan_applications", "cdas_collection_plan")
    op.drop_column("direct_loan_applications", "cdas_collection_enabled")
