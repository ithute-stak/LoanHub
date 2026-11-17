"""Fail-closed PostgreSQL deployment gate for official document issuance.

This is a database-role inspection, not a substitute for membership checks,
RLS tests, protected object storage or a feature flag. It deliberately refuses
to certify an owner or BYPASSRLS session even if policies exist.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


_REQUIRED_TABLES = ("document_issuances", "document_issuance_events")


def document_issuance_database_readiness(db: Session) -> tuple[bool, tuple[str, ...]]:
    """Inspect the *actual connected runtime role* and public-schema tables."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return False, ("postgresql_required",)
    issues: list[str] = []
    role = db.execute(text("""
        SELECT current_user AS role_name, r.rolsuper, r.rolbypassrls
        FROM pg_roles r WHERE r.rolname = current_user
    """)).mappings().one_or_none()
    if not role or role["rolsuper"] or role["rolbypassrls"]:
        issues.append("runtime_role_bypasses_rls")

    rows = db.execute(text("""
        SELECT c.relname AS table_name,
               pg_get_userbyid(c.relowner) AS owner_name,
               c.relrowsecurity AS rls_enabled,
               (SELECT count(*) FROM pg_policies p
                WHERE p.schemaname = 'public' AND p.tablename = c.relname
                  AND p.policyname IN (
                      c.relname || '_tenant_select',
                      c.relname || '_tenant_insert'
                  )) AS policy_count,
               has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
               has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert,
               has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update,
               has_table_privilege(current_user, c.oid, 'DELETE') AS can_delete
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND c.relname IN ('document_issuances', 'document_issuance_events')
    """)).mappings().all()
    tables = {r["table_name"]: r for r in rows}
    for name in _REQUIRED_TABLES:
        row = tables.get(name)
        if row is None:
            issues.append(f"{name}:missing")
            continue
        if role and row["owner_name"] == role["role_name"]:
            issues.append(f"{name}:runtime_owns_table")
        if not row["rls_enabled"] or row["policy_count"] != 2:
            issues.append(f"{name}:rls_policies_unavailable")
        if not row["can_select"] or not row["can_insert"]:
            issues.append(f"{name}:required_privilege_missing")
        if row["can_update"] or row["can_delete"]:
            issues.append(f"{name}:write_privilege_too_broad")
    return not issues, tuple(issues)


def require_document_issuance_database_ready(db: Session) -> None:
    """Only approve issuing if the connected DB role meets the strict contract."""
    ready, problems = document_issuance_database_readiness(db)
    if not ready:
        raise PermissionError(
            "Document issuance database security is not ready: "
            + ", ".join(problems)
        )
