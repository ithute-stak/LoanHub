"""PostgreSQL schema invariants for future Principal x% migration.

This is a pure schema specification used to test migration requirements.
It intentionally does not execute DDL or guess the current Alembic head.
"""
COMPANY_SETTINGS_CHECKS = (
    "default_model IN ('existing', 'principal_x')",
    "NOT enable_live_collections OR allow_new_loans",
    "NOT enable_live_collections OR default_model = 'principal_x'",
)

LOAN_ASSIGNMENT_CHECKS = (
    "payment_model IN ('existing', 'principal_x')",
)

# The eventual migration must also enforce same-company loan ownership,
# e.g. with a composite foreign key after checking the actual loan schema.
# An independent FK to loans and FK to companies is NOT sufficient.
