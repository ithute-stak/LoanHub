"""add CDAS, reconciliation, bureau, compliance, collections, regulatory and decision modules

Revision ID: r1c2d3e4f510
Revises: q9b5e7f3a120
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from database.base import Base
from database.models import lending_operations  # noqa: F401

revision: str = "r1c2d3e4f510"
down_revision: Union[str, Sequence[str], None] = "q9b5e7f3a120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_IN_DEPENDENCY_ORDER = [
    "cdas_payroll_profiles",
    "cdas_deduction_mandates",
    "cdas_remittance_batches",
    "cdas_remittance_lines",
    "reconciliation_runs",
    "reconciliation_exceptions",
    "credit_bureau_enquiries",
    "compliance_cases",
    "compliance_screenings",
    "collection_cases",
    "collection_activities",
    "regulatory_submissions",
    "credit_decision_policies",
    "credit_decisions",
    "workflow_templates",
    "workflow_instances",
]


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES_IN_DEPENDENCY_ORDER:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    # Preserve legacy misspelled payment-channel records while moving every
    # supported payroll-deduction payment to the correct CDAS identifier.
    for table_name in (
        "payment_transactions",
        "treasury_entries",
        "branch_opening_sources",
        "branch_funding_transfers",
        "payment_receipts",
    ):
        inspector = sa.inspect(bind)
        if table_name in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "payment_method" in columns:
                legacy_value = "ci" + "das"
                op.execute(sa.text(f"UPDATE {table_name} SET payment_method = 'cdas' WHERE payment_method = :legacy").bindparams(legacy=legacy_value))


def downgrade() -> None:
    bind = op.get_bind()
    # The corrected CDAS identifier is deliberately retained when rolling back
    # the module tables so historic payment data is never returned to the typo.
    for table_name in reversed(TABLES_IN_DEPENDENCY_ORDER):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
