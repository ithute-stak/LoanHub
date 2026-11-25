-- Draft only: a delegated, role-bound authorization lock for company-letter issuance.
-- Do not install or grant EXECUTE in production until independently reviewed.
-- Lock ownership remains in the invoking SQL transaction until COMMIT/ROLLBACK.
BEGIN;

DO $preflight$
BEGIN
    IF to_regclass('public.document_issuer_role_tenants') IS NULL
       OR to_regclass('public.users') IS NULL
       OR to_regclass('public.loan_companies') IS NULL
       OR to_regclass('public.company_staff') IS NULL THEN
        RAISE EXCEPTION 'Protected issuer mapping and authorization tables are required';
    END IF;
END
$preflight$;

CREATE OR REPLACE FUNCTION public.lock_document_issuer_authorization(
    p_user_id uuid, p_company_id uuid, p_staff_id uuid
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $issuer_authorization$
DECLARE
    v_staff_role text;
BEGIN
    IF p_user_id IS NULL OR p_company_id IS NULL OR p_staff_id IS NULL THEN
        RAISE EXCEPTION 'Issuer identity, company and membership are required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles r
         WHERE r.rolname = session_user
           AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
           AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication
    ) THEN
        RAISE EXCEPTION 'Untrusted issuer database login';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.document_issuer_role_tenants b
         WHERE b.login_name = session_user AND b.company_id = p_company_id
    ) THEN
        RAISE EXCEPTION 'Issuer login not bound to company';
    END IF;

    -- The fixed lock order limits deadlocks with other issuance transactions.
    -- No rows are modified. Direct source-table UPDATE is unnecessary.
    PERFORM 1 FROM public.users u
     WHERE u.id = p_user_id AND u.is_active IS TRUE
       AND u.must_change_password IS FALSE
     FOR SHARE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Issuer account inactive or unavailable';
    END IF;

    PERFORM 1 FROM public.loan_companies c
     WHERE c.id = p_company_id AND c.is_active IS TRUE
       AND c.status::text = 'APPROVED'
     FOR SHARE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Issuer company inactive or unapproved';
    END IF;

    SELECT s.role::text INTO v_staff_role
      FROM public.company_staff s
     WHERE s.id = p_staff_id AND s.user_id = p_user_id
       AND s.company_id = p_company_id AND s.is_active IS TRUE
       AND s.role::text IN ('COMPANY_OWNER', 'COMPANY_ADMIN')
     FOR SHARE NOWAIT;
    IF v_staff_role IS NULL THEN
        RAISE EXCEPTION 'Issuer management membership missing or revoked';
    END IF;
    RETURN true;
END
$issuer_authorization$;

REVOKE ALL ON FUNCTION public.lock_document_issuer_authorization(uuid, uuid, uuid)
    FROM PUBLIC;
DO $revoke$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'loanhub_app') THEN
        REVOKE ALL ON FUNCTION public.lock_document_issuer_authorization(uuid,uuid,uuid)
            FROM loanhub_app;
    END IF;
END
$revoke$;
-- No EXECUTE grant in this script. An independent reviewer must authorize
-- a specific issuer login after negative cross-company and revocation tests.
COMMIT;
