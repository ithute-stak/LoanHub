-- Draft, reviewed database primitive for tenant-bound official-letter locking.
-- DO NOT apply from normal LoanHub application migrations or enable issuance.
-- Install only as a trusted database owner after protected role-to-company
-- mapping is provisioned. EXECUTE permission is NOT granted to issuer roles
-- here: grant it only to an individually reviewed login with a fixed mapping.
--
-- A SECURITY DEFINER lock avoids granting UPDATE on workspace_documents.
-- The caller must hold the same SQL transaction through audit COMMIT.
BEGIN;

DO $preflight$
BEGIN
    IF to_regclass('public.document_issuer_role_tenants') IS NULL THEN
        RAISE EXCEPTION 'Protected issuer-login/company mapping is required';
    END IF;
    IF to_regclass('public.workspace_documents') IS NULL THEN
        RAISE EXCEPTION 'Workspace source table is required';
    END IF;
END
$preflight$;

CREATE OR REPLACE FUNCTION public.lock_document_issuer_workspace_source(
    p_document_id uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $issuer_lock$
DECLARE
    v_company_id uuid;
    v_document_id uuid;
BEGIN
    IF p_document_id IS NULL THEN
        RAISE EXCEPTION 'Source document identity required';
    END IF;

    -- The caller cannot choose session_user by changing LoanHub tenant GUCs.
    -- A privileged/role-switched login must not use this delegated lock.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles r
         WHERE r.rolname = session_user
           AND r.rolcanlogin
           AND NOT r.rolsuper
           AND NOT r.rolbypassrls
           AND NOT r.rolcreaterole
           AND NOT r.rolcreatedb
           AND NOT r.rolreplication
    ) THEN
        RAISE EXCEPTION 'Untrusted issuer login';
    END IF;

    SELECT b.company_id INTO v_company_id
      FROM public.document_issuer_role_tenants b
     WHERE b.login_name = session_user;
    IF v_company_id IS NULL THEN
        RAISE EXCEPTION 'Issuer company binding missing';
    END IF;

    -- Lock only a current draft from the login's independently bound tenant.
    -- Document row FOR UPDATE also prevents concurrent signature inserts
    -- that require a foreign-key KEY SHARE on that row.
    SELECT d.id INTO v_document_id
      FROM public.workspace_documents d
     WHERE d.id = p_document_id
       AND d.company_id = v_company_id
       AND d.is_deleted = false
       AND d.status = 'draft'
       AND d.finalized_at IS NULL
       AND d.version >= 1
       AND NOT EXISTS (
           SELECT 1 FROM public.workspace_document_signatures s
            WHERE s.document_id = d.id
       )
     FOR UPDATE OF d NOWAIT;

    IF v_document_id IS NULL THEN
        RAISE EXCEPTION 'Tenant-bound unsigned draft not available for locking';
    END IF;
    RETURN v_document_id;
END
$issuer_lock$;

-- PostgreSQL normally grants EXECUTE on new functions to PUBLIC by default.
-- Remove this broad default before committing the transaction.
REVOKE ALL ON FUNCTION public.lock_document_issuer_workspace_source(uuid) FROM PUBLIC;
DO $revoke$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'loanhub_app') THEN
        REVOKE ALL ON FUNCTION public.lock_document_issuer_workspace_source(uuid) FROM loanhub_app;
    END IF;
END
$revoke$;

-- No GRANT EXECUTE to issuer roles here: role provisioning is gated.
COMMIT;
