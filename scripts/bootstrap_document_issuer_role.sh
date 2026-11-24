#!/usr/bin/env sh
# One-time reviewed bootstrap for an isolated official-document issuer login.
# Requires owner credentials supplied by the operator OUTSIDE this repository.
# No approver records, API routes, certificates or S3 buckets are created.
set -eu

: "${DB_NAME:?DB_NAME required}"
: "${DB_USER:?DB_USER must be the PostgreSQL schema owner}"
: "${DB_PASSWORD:?DB_PASSWORD required}"
: "${ISSUER_DB_PASSWORD:?ISSUER_DB_PASSWORD required}"
: "${ISSUER_DB_USER:=loanhub_document_issuer}"

case "$ISSUER_DB_USER" in
  *[!a-z0-9_]*|'') echo "Invalid dedicated issuer role" >&2; exit 2 ;;
esac
if [ "$ISSUER_DB_USER" = "$DB_USER" ] || [ "$ISSUER_DB_USER" = "${DB_RUNTIME_USER:-}" ]; then
  echo "Issuer login must differ from schema owner and ordinary application login" >&2
  exit 2
fi
export PGPASSWORD="$DB_PASSWORD"

# NOTE: this script must be run with the database-owner connection available,
# outside the regular LoanHub application DB pool.
psql --host "${DB_HOST:-db}" --port "${DB_PORT:-5432}" \
  --username "$DB_USER" --dbname "$DB_NAME" --set=ON_ERROR_STOP=1 \
  --set=issuer_user="$ISSUER_DB_USER" --set=issuer_password="$ISSUER_DB_PASSWORD" <<'SQL'
-- Refuse privileged issuer grants until *all* relevant tenant-owned sources
-- enforce RLS. A restricted SQL role with UPDATE on non-RLS source tables
-- would otherwise be able to alter documents belonging to other tenants.
DO $preflight$
DECLARE
    missing TEXT;
BEGIN
    SELECT string_agg(name, ', ' ORDER BY name) INTO missing
    FROM unnest(ARRAY[
        'users', 'loan_companies', 'company_staff', 'workspace_documents',
        'workspace_document_signatures',
        'document_stamp_approvals', 'document_stamp_approval_revocations',
        'document_issuances', 'document_issuance_events'
    ]) AS wanted(name)
    LEFT JOIN pg_class AS c
      ON c.relname = wanted.name AND c.relnamespace = 'public'::regnamespace
    WHERE c.oid IS NULL OR c.relrowsecurity IS NOT TRUE;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'Issuer bootstrap refused: missing tenant RLS on %', missing;
    END IF;
END
$preflight$;

BEGIN;
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION PASSWORD %L',
              :'issuer_user', :'issuer_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'issuer_user')
\gexec
SELECT format('ALTER ROLE %I WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION PASSWORD %L',
              :'issuer_user', :'issuer_password')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'issuer_user')
\gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'issuer_user')
\gexec
-- Clear any older blanket privileges before granting the exact issuer set.
SELECT format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', :'issuer_user')
\gexec
SELECT format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', :'issuer_user')
\gexec
-- Approval history stays read-only even to the issuer.
SELECT format('GRANT SELECT ON TABLE document_stamp_approvals, document_stamp_approval_revocations TO %I', :'issuer_user')
\gexec
-- Issuance records are append-only.
SELECT format('GRANT SELECT, INSERT ON TABLE document_issuances, document_issuance_events TO %I', :'issuer_user')
\gexec
-- Read source tables only when tenant RLS has been verified. Never grant
-- direct UPDATE to a privileged document issuer: the previous row-lock grant
-- permitted mutation of documents and staff/user authorization fields.
-- Source locking requires a separately reviewed SECURITY DEFINER function
-- whose tenant identity comes from the protected login/company mapping.
SELECT format('GRANT SELECT ON TABLE users, loan_companies, company_staff, workspace_documents TO %I', :'issuer_user')
\gexec
-- Signature read required to fail closed on signed source rows.
SELECT format('GRANT SELECT ON TABLE workspace_document_signatures TO %I', :'issuer_user')
\gexec
-- Tenant isolation must still be proven with RLS and negative integration
-- tests, not inferred from these SQL grants.
COMMIT;
SELECT rolname,rolsuper,rolbypassrls,rolcanlogin,rolcreatedb,rolcreaterole,rolreplication
FROM pg_roles WHERE rolname = :'issuer_user';
SQL
echo "Dedicated issuer role bootstrapped. Do NOT activate issuance until RLS, revocation, approval, bucket and transaction acceptance pass."
