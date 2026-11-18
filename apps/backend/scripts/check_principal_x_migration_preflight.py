"""Alembic migration preflight for Principal x% payment-model tables.

Run from apps/backend with:
    python -m scripts.check_principal_x_migration_preflight

This script is read-only. It deliberately does not generate a revision,
run upgrades, or guess a migration parent.
"""
from __future__ import annotations

import sys


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
    if len(heads) != 1:
        print("BLOCKED: expected exactly one verified Alembic head")
        return 1

    required = {
        "company_payment_model_settings",
        "loan_payment_model_assignments",
        "client_company_loan",
    }
    missing = required.difference(Base.metadata.tables)
    if missing:
        print("BLOCKED: ORM tables not registered:", ", ".join(sorted(missing)))
        return 1

    assignments = Base.metadata.tables["loan_payment_model_assignments"]
    composite_fk = any(
        {element.parent.name for element in constraint.elements}
        == {"loan_id", "company_id"}
        and {element.column.table.name for element in constraint.elements}
        == {"client_company_loan"}
        for constraint in assignments.foreign_key_constraints
    )
    if not composite_fk:
        print("BLOCKED: loan/company ownership composite foreign key missing")
        return 1

    print("PREFLIGHT OK: verified head =", heads[0])
    print("Next: generate a reviewed migration against this head; do not deploy automatically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
