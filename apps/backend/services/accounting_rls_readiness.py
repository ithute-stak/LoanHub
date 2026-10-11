"""Read-only inspection of PostgreSQL accounting ledger RLS deployment readiness.

Never changes policies, grants, roles, accounting transactions or sessions.
"""
from __future__ import annotations

from sqlalchemy import text

ACCOUNTING_TABLES = ("accounting_accounts", "journal_entries", "journal_lines")
REQUIRED_COMMANDS = ("SELECT", "INSERT", "UPDATE", "DELETE")


def accounting_rls_readiness(db) -> dict:
    """Check installed production-table RLS and policies without modifying them."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        raise ValueError("PostgreSQL is required for accounting RLS readiness")
    tables = db.execute(text("""
        SELECT c.relname AS name, c.relrowsecurity AS enabled,
               c.relforcerowsecurity AS forced
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind IN ('r', 'p')
          AND c.relname IN ('accounting_accounts', 'journal_entries', 'journal_lines')
    """)).mappings().all()
    policies = db.execute(text("""
        SELECT tablename, cmd, roles, qual, with_check
        FROM pg_policies
        WHERE schemaname = current_schema()
          AND tablename IN ('accounting_accounts', 'journal_entries', 'journal_lines')
    """)).mappings().all()
    table_by_name = {row["name"]: row for row in tables}
    findings = []
    for name in ACCOUNTING_TABLES:
        row = table_by_name.get(name)
        associated = [p for p in policies if p["tablename"] == name]
        enabled = bool(row and row["enabled"])
        commands = {p["cmd"].upper() for p in associated}
        # ALL policies can cover every command; this is coverage, not a proof
        # that predicates/role grants isolate tenants correctly.
        missing = [] if "ALL" in commands else sorted(set(REQUIRED_COMMANDS) - commands)
        if not row:
            findings.append(f"{name}:table_missing")
        if not enabled:
            findings.append(f"{name}:rls_disabled")
        if missing:
            findings.append(f"{name}:policy_commands_missing:{','.join(missing)}")
    return {
        "ready": not findings,
        "findings": findings,
        "tables": {
            name: {
                "exists": name in table_by_name,
                "rls_enabled": bool(table_by_name.get(name, {}).get("enabled")),
                "rls_forced": bool(table_by_name.get(name, {}).get("forced")),
                "policy_commands": sorted({p["cmd"] for p in policies if p["tablename"] == name}),
            } for name in ACCOUNTING_TABLES
        },
        "advisory_only": True,
        "warning": "Policy coverage does not prove tenant isolation; restricted-role behavioral tests are required.",
    }
