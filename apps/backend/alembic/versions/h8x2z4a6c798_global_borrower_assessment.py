"""Share borrower assessment data across LoanHub companies.

Revision ID: h8x2z4a6c798
Revises: g7w1y3z5b687

Borrower identity and assessment facts belong to the system-wide borrower.
Company applications, affordability decisions, contracts and agreements remain
tenant scoped in their existing tables.
"""

from alembic import op

revision = "h8x2z4a6c798"
down_revision = "g7w1y3z5b687"
branch_labels = None
depends_on = None


_SHARED_TABLES = (
    "borrower_kyc_profiles",
    "borrower_employment_profiles",
    "borrower_income_sources",
    "borrower_expenses",
    "borrower_debt_obligations",
    "borrower_debt_obligation_events",
    "borrower_bank_accounts",
)


def _make_company_provenance_nullable(table_name: str) -> None:
    constraint_name = f"{table_name}_company_id_fkey"
    op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    op.alter_column(table_name, "company_id", nullable=True)
    op.create_foreign_key(
        constraint_name,
        table_name,
        "loan_companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _restore_company_ownership(table_name: str) -> None:
    constraint_name = f"{table_name}_company_id_fkey"
    op.execute(f"DELETE FROM {table_name} WHERE company_id IS NULL")
    op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    op.alter_column(table_name, "company_id", nullable=False)
    op.create_foreign_key(
        constraint_name,
        table_name,
        "loan_companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    # The pre-existing tenant-scoped schema can contain one row per lender.
    # Preserve the latest canonical KYC and employment records before applying
    # the borrower-wide uniqueness constraints.
    op.execute(
        """
        DELETE FROM borrower_kyc_profiles older
        USING borrower_kyc_profiles newer
        WHERE older.borrower_id = newer.borrower_id
          AND (
            older.updated_at < newer.updated_at
            OR (older.updated_at = newer.updated_at AND older.id::text < newer.id::text)
          )
        """
    )
    op.execute(
        """
        DELETE FROM borrower_employment_profiles older
        USING borrower_employment_profiles newer
        WHERE older.borrower_id = newer.borrower_id
          AND (
            older.updated_at < newer.updated_at
            OR (older.updated_at = newer.updated_at AND older.id::text < newer.id::text)
          )
        """
    )

    op.drop_constraint(
        "uq_kyc_company_borrower",
        "borrower_kyc_profiles",
        type_="unique",
    )
    op.drop_constraint(
        "uq_employment_company_borrower",
        "borrower_employment_profiles",
        type_="unique",
    )
    op.drop_constraint(
        "uq_bank_company_borrower",
        "borrower_bank_accounts",
        type_="unique",
    )

    for table_name in _SHARED_TABLES:
        _make_company_provenance_nullable(table_name)

    op.create_unique_constraint(
        "uq_kyc_borrower",
        "borrower_kyc_profiles",
        ["borrower_id"],
    )
    op.create_unique_constraint(
        "uq_employment_borrower",
        "borrower_employment_profiles",
        ["borrower_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_employment_borrower",
        "borrower_employment_profiles",
        type_="unique",
    )
    op.drop_constraint(
        "uq_kyc_borrower",
        "borrower_kyc_profiles",
        type_="unique",
    )

    for table_name in reversed(_SHARED_TABLES):
        _restore_company_ownership(table_name)

    # Multiple banking rows are valid in the shared model. The historical
    # schema allowed one row per company and borrower, so retain the latest.
    op.execute(
        """
        DELETE FROM borrower_bank_accounts older
        USING borrower_bank_accounts newer
        WHERE older.company_id = newer.company_id
          AND older.borrower_id = newer.borrower_id
          AND (
            older.updated_at < newer.updated_at
            OR (older.updated_at = newer.updated_at AND older.id::text < newer.id::text)
          )
        """
    )

    op.create_unique_constraint(
        "uq_bank_company_borrower",
        "borrower_bank_accounts",
        ["company_id", "borrower_id"],
    )
    op.create_unique_constraint(
        "uq_employment_company_borrower",
        "borrower_employment_profiles",
        ["company_id", "borrower_id"],
    )
    op.create_unique_constraint(
        "uq_kyc_company_borrower",
        "borrower_kyc_profiles",
        ["company_id", "borrower_id"],
    )
