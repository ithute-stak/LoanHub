"""Fail-closed, read-only approval lookup for official company stamp issuance.

NON-ROUTED. The stamp approval registry/schema is NOT yet deployed. This
helper deliberately refuses to authorize issuance until a separately reviewed
tenant-isolated table, SELECT-only runtime grants and the connected tenant
session can all be verified. The approval row MUST NOT come from request JSON.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.document_issuance_stamp_approval import (
    ApprovedCompanyStamp, require_approved_company_stamp_snapshot,
)


def lookup_approved_stamp_from_database(
    *, db: Session, company, authenticated_tenant_id: UUID,
    issuer_user_id: UUID, configuration_version: int,
) -> ApprovedCompanyStamp:
    """Inspect connected PostgreSQL role and query one company approval.

    No INSERT/UPDATE/DELETE calls. SQL ownership and RLS are inspected on the
    connected DB, not inferred from a feature flag or a test fixture.
    """
    if not isinstance(authenticated_tenant_id, UUID) or not isinstance(issuer_user_id, UUID):
        raise PermissionError("Verified tenant and actor required")
    if type(configuration_version) is not int or configuration_version < 1:
        raise PermissionError("Valid approved stamp version required")
    if db.bind is None or db.bind.dialect.name != "postgresql":
        raise PermissionError("Protected PostgreSQL stamp approval registry required")
    security = db.execute(text("""
        SELECT c.relrowsecurity AS rls_enabled,
               pg_get_userbyid(c.relowner) = current_user AS runtime_owns_table,
               r.rolsuper AS superuser, r.rolbypassrls AS bypass_rls,
               has_table_privilege(current_user,c.oid,'SELECT') AS can_select,
               has_table_privilege(current_user,c.oid,'INSERT') AS can_insert,
               has_table_privilege(current_user,c.oid,'UPDATE') AS can_update,
               has_table_privilege(current_user,c.oid,'DELETE') AS can_delete,
               current_setting('loanhub.actor_scope', true) AS actor_scope,
               current_setting('loanhub.company_id', true) AS context_company_id,
               current_setting('loanhub.user_id', true) AS context_user_id,
               EXISTS(
                   SELECT 1 FROM pg_policies p
                   WHERE p.schemaname='public'
                     AND p.tablename='document_stamp_approvals'
                     AND p.policyname='document_stamp_approvals_tenant_select'
                     AND p.cmd='SELECT'
               ) AS tenant_policy,
               EXISTS (
                   SELECT 1 FROM pg_class rc JOIN pg_namespace rn ON rn.oid=rc.relnamespace
                   WHERE rn.nspname='public' AND rc.relkind IN ('r','p')
                     AND rc.relname='document_stamp_approval_revocations'
                     AND rc.relrowsecurity
                     AND pg_get_userbyid(rc.relowner) <> current_user
                     AND has_table_privilege(current_user,rc.oid,'SELECT')
                     AND NOT has_table_privilege(current_user,rc.oid,'INSERT')
                     AND NOT has_table_privilege(current_user,rc.oid,'UPDATE')
                     AND NOT has_table_privilege(current_user,rc.oid,'DELETE')
                     AND EXISTS (
                         SELECT 1 FROM pg_policies p
                         WHERE p.schemaname='public'
                           AND p.tablename='document_stamp_approval_revocations'
                           AND p.policyname='document_stamp_approval_revocations_tenant_select'
                           AND p.cmd='SELECT'
                     )
               ) AS revocation_registry_ready
        FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_roles r ON r.rolname=current_user
        WHERE n.nspname='public' AND c.relkind IN ('r','p')
          AND c.relname='document_stamp_approvals'
    """)).mappings().one_or_none()
    if (not security or not security["rls_enabled"]
            or security["runtime_owns_table"] or security["superuser"]
            or security["bypass_rls"] or not security["can_select"]
            or security["can_insert"] or security["can_update"]
            or security["can_delete"] or not security["tenant_policy"]
            or not security["revocation_registry_ready"]
            or security["actor_scope"] != "tenant"
            or security["context_company_id"] != str(authenticated_tenant_id)
            or security["context_user_id"] != str(issuer_user_id)):
        raise PermissionError("Stamp approval registry SQL security is not ready")

    row = db.execute(text("""
        SELECT id, company_id, configuration_version, snapshot_sha256_hex,
               approved_by_user_id, approved_at, expires_at, status
        FROM document_stamp_approvals
        WHERE company_id=:company_id
          AND configuration_version=:configuration_version
    """), {
        "company_id": str(authenticated_tenant_id),
        "configuration_version": configuration_version,
    }).mappings().one_or_none()
    if not row:
        raise PermissionError("No authoritative stamp approval for this version")
    if not isinstance(row["id"], UUID):
        raise PermissionError("Authoritative approval record ID required")
    revoked = db.execute(text("""
        SELECT id FROM document_stamp_approval_revocations
        WHERE company_id=:company_id AND approval_id=:approval_id
        LIMIT 1
    """), {"company_id": str(authenticated_tenant_id),
           "approval_id": str(row["id"])}).mappings().one_or_none()
    if revoked:
        raise PermissionError("Company stamp approval has been revoked")
    approval = ApprovedCompanyStamp(
        tenant_id=row["company_id"],
        configuration_version=row["configuration_version"],
        snapshot_sha256_hex=row["snapshot_sha256_hex"],
        approved_by_user_id=row["approved_by_user_id"],
        approved_at=row["approved_at"],
        expires_at=row["expires_at"],
        status=row["status"],
    )
    require_approved_company_stamp_snapshot(
        company=company, authenticated_tenant_id=authenticated_tenant_id,
        approval=approval, issuer_user_id=issuer_user_id,
        configuration_version=configuration_version,
    )
    return approval
