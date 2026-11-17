-- LoanHub document issuance RLS HARDENING TEMPLATE (NOT APPLIED).
-- Run only as part of a reviewed Alembic migration after verifying current
-- migration head, DB ownership, app DB role and all existing policies.
--
-- The server MUST bind loanhub.actor_scope, loanhub.company_id and
-- loanhub.user_id from authenticated TenantContext, never client headers.
-- The application role must not be table owner, superuser or BYPASSRLS.
-- Existing production migrations must apply this with table creation.
--
-- This policy deliberately gives no blanket platform bypass.
-- Public QR verification should use narrowly scoped authenticated backend
-- functions and privacy-limited outputs, not unrestricted table SELECT.

ALTER TABLE document_issuances ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_issuances FORCE ROW LEVEL SECURITY;
ALTER TABLE document_issuance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_issuance_events FORCE ROW LEVEL SECURITY;

CREATE POLICY document_issuances_tenant_select ON document_issuances
    FOR SELECT USING (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = nullif(current_setting('loanhub.company_id', true), '')
    );

CREATE POLICY document_issuances_tenant_insert ON document_issuances
    FOR INSERT WITH CHECK (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = nullif(current_setting('loanhub.company_id', true), '')
        AND issued_by_user_id::text = nullif(current_setting('loanhub.user_id', true), '')
        AND current_setting('loanhub.role', true) IN ('company_owner', 'company_admin')
    );

CREATE POLICY document_issuance_events_tenant_select ON document_issuance_events
    FOR SELECT USING (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = nullif(current_setting('loanhub.company_id', true), '')
    );

CREATE POLICY document_issuance_events_tenant_insert ON document_issuance_events
    FOR INSERT WITH CHECK (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = nullif(current_setting('loanhub.company_id', true), '')
        AND actor_user_id::text = nullif(current_setting('loanhub.user_id', true), '')
        AND current_setting('loanhub.role', true) IN ('company_owner', 'company_admin')
        AND EXISTS (
            SELECT 1 FROM document_issuances i
            WHERE i.id = issuance_id AND i.company_id = company_id
        )
    );

-- IMPORTANT: there is intentionally no UPDATE or DELETE policy.
-- Current issuance status is mutable by business process; implement an
-- audited SECURITY DEFINER transition function with an explicit fixed
-- search_path, authorization, event writing and tenant checks before enabling
-- revocation/supersession. Never grant unrestricted UPDATE/DELETE.

-- Role-level grants should be explicit in deployment, e.g.:
-- REVOKE ALL ON document_issuances, document_issuance_events FROM PUBLIC;
-- GRANT SELECT, INSERT ON document_issuances, document_issuance_events TO <verified_app_role>;
-- Never use an app role with BYPASSRLS.
-- DENY implicit direct UPDATE/DELETE at role level.

-- Security review:
-- 1. Test direct SQL as app role in two authenticated tenant scopes.
-- 2. Test missing context, platform scope, forged company_id and role.
-- 3. Test SELECT/INSERT/UPDATE/DELETE denial with actual PostgreSQL.
-- 4. Verify event immutability and ownership/privileges.
-- 5. Ensure canonical PDF object cannot be mutated/deleted.
