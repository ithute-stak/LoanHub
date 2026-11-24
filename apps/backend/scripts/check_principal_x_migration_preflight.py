"""Alembic migration preflight for Principal x% payment-model tables.

Run from apps/backend with:
    python -m scripts.check_principal_x_migration_preflight

This script is read-only. It deliberately does not generate a revision,
run upgrades, or guess a migration parent.
"""
from __future__ import annotations

import sys


def verify_migration_metadata(heads, metadata) -> list[str]:
    errors = []
    if len(heads) != 1:
        errors.append("Expected exactly one Alembic head")
    required = {"company_payment_model_settings", "loan_payment_model_assignments", "client_company_loan"}
    missing = required.difference(metadata.tables)
    if missing:
        errors.append("Missing ORM tables: " + ", ".join(sorted(missing)))
    if "loan_payment_model_assignments" in metadata.tables:
        assignments = metadata.tables["loan_payment_model_assignments"]
        composite_fk = any(
            {element.parent.name for element in constraint.elements} == {"loan_id", "company_id"}
            and {element.column.table.name for element in constraint.elements} == {"client_company_loan"}
            for constraint in assignments.foreign_key_constraints
        )
        if not composite_fk:
            errors.append("Loan/company ownership composite foreign key missing")
    return errors


def main() -> int:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from database.base import Base
        import database.models  # noqa: F401
    except ImportError as exc:
        print(f"PRECHECK BLOCKED: missing dependency: {exc}", file=sys.stderr)
        return 2

    cfg = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(cfg)
    heads = scripts.get_heads()
    print("Alembic heads:", ", ".join(heads) or "<none>")
    errors = verify_migration_metadata(heads, Base.metadata)
    if errors:
        for error in errors:
            print("BLOCKED:", error)
        return 1

    print("PREFLIGHT OK: verified head =", heads[0])
    print("Next: generate a reviewed migration against this head; do not deploy automatically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
