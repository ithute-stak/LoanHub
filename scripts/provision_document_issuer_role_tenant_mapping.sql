-- Manual, reviewed migration prerequisite for official-letter issuance.
-- Do NOT run as the ordinary application login. This file creates the
-- protected role-to-company mapping only: it grants no issuer privileges,
-- adds no rows, alters no existing LoanHub tables, and enables no routes.
--
-- Each separately provisioned issuer login MUST be bound to one company by
-- an independently authorized database administrator. Never accept a company
-- ID from a caller-controlled session setting as proof of this binding.
BEGIN;

CREATE TABLE IF NOT EXISTS public.document_issuer_role_tenants (
    login_name name PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES public.loan_companies(id) ON DELETE RESTRICT,
    provisioned_at timestamptz NOT NULL DEFAULT now()
);

-- Fail closed on an unexpected schema left by an earlier deployment.
DO $verify$
DECLARE
    required_columns integer;
BEGIN
    SELECT count(*) INTO required_columns
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'document_issuer_role_tenants'
       AND ((column_name = 'login_name' AND data_type = 'name')
         OR (column_name = 'company_id' AND data_type = 'uuid')
         OR (column_name = 'provisioned_at' AND data_type = 'timestamp with time zone'));
    IF required_columns <> 3 THEN
        RAISE EXCEPTION 'Unexpected document issuer mapping schema';
    END IF;
END
$verify$;

REVOKE ALL ON TABLE public.document_issuer_role_tenants FROM PUBLIC;
-- No GRANT SELECT, INSERT, UPDATE or DELETE to any issuer here.
-- Review the exact per-company issuer login and separately GRANT SELECT
-- only after its CREATE ROLE, isolation, and revocation tests pass.

COMMIT;
