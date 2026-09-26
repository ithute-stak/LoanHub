"""version collection treatment policy uniqueness

Revision ID: i3p4r5t6u702
Revises: i3p4r5t6u701
Create Date: 2026-09-26
"""

from alembic import op


revision = "i3p4r5t6u702"
down_revision = "i3p4r5t6u701"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_collection_treatment_policy_company_name",
        "collection_treatment_policies",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_collection_treatment_policy_company_name_version",
        "collection_treatment_policies",
        ["company_id", "name", "version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_collection_treatment_policy_company_name_version",
        "collection_treatment_policies",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_collection_treatment_policy_company_name",
        "collection_treatment_policies",
        ["company_id", "name"],
    )
