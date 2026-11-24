"""Fail-closed, database-role-bound tenant lookup for a future dedicated issuer.

Unlike a tenant GUC, the mapping is keyed by PostgreSQL session_user, which
cannot be selected by a SQL client. The mapping must be owned/provisioned by
a trusted migration administrator; issuer logins must have SELECT only.

This helper is NOT wired into public routes. The role and protected mapping
table must be provisioned and independently audited before activation.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text


def require_issuer_role_tenant_binding(*, db, authenticated_tenant_id: UUID) -> None:
    """Require a non-privileged issuer login bound to the requested company.

    Fail closed if the protected mapping has not been installed or if a role
    tries to impersonate another tenant by changing custom GUCs.
    """
    if not isinstance(authenticated_tenant_id, UUID):
        raise PermissionError("Issuer tenant identity is required")
    if db.bind is None or db.bind.dialect.name != "postgresql":
        raise PermissionError("PostgreSQL issuer connection required")

    identity = db.execute(text("""
        SELECT session_user AS login_name,
               current_user AS active_role,
               r.rolsuper AS is_superuser,
               r.rolbypassrls AS bypasses_rls,
               r.rolcreaterole AS creates_roles
          FROM pg_roles r
         WHERE r.rolname = session_user
    """)).mappings().one_or_none()
    if (identity is None or identity["login_name"] != identity["active_role"]
            or identity["is_superuser"] is not False
            or identity["bypasses_rls"] is not False
            or identity["creates_roles"] is not False):
        raise PermissionError("Untrusted issuer database role")

    # The mapping is not a tenant GUC. Its rows and privileges must be
    # provisioned independently, and the issuer must not own or write it.
    mapping = db.execute(text("""
        SELECT c.relowner = (SELECT oid FROM pg_roles WHERE rolname = session_user)
                   AS owns_mapping,
               has_table_privilege(session_user, c.oid, 'INSERT') AS can_insert,
               has_table_privilege(session_user, c.oid, 'UPDATE') AS can_update,
               has_table_privilege(session_user, c.oid, 'DELETE') AS can_delete
          FROM pg_class c
         WHERE c.oid = to_regclass('public.document_issuer_role_tenants')
    """)).mappings().one_or_none()
    if (mapping is None or mapping["owns_mapping"] is not False
            or mapping["can_insert"] is not False
            or mapping["can_update"] is not False
            or mapping["can_delete"] is not False):
        raise PermissionError("Issuer tenant mapping is not protected")

    company = db.execute(text("""
        SELECT company_id
          FROM public.document_issuer_role_tenants
         WHERE login_name = session_user
    """)).scalar_one_or_none()
    if company != authenticated_tenant_id:
        raise PermissionError("Issuer SQL login is not bound to authenticated company")
