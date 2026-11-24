#!/usr/bin/env sh
set -eu

: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER (database owner) is required}"
: "${DB_PASSWORD:?DB_PASSWORD (database owner password) is required}"
: "${DB_RUNTIME_USER:?DB_RUNTIME_USER is required}"
: "${DB_RUNTIME_PASSWORD:?DB_RUNTIME_PASSWORD is required}"

case "$DB_USER" in
  *[!A-Za-z0-9_]*|'') echo "DB_USER must contain only letters, digits and underscore" >&2; exit 2 ;;
esac
case "$DB_RUNTIME_USER" in
  *[!A-Za-z0-9_]*|'') echo "DB_RUNTIME_USER must contain only letters, digits and underscore" >&2; exit 2 ;;
esac

if [ "$DB_RUNTIME_USER" = "$DB_USER" ]; then
  echo "DB_RUNTIME_USER must be different from the database owner DB_USER" >&2
  exit 2
fi

export PGPASSWORD="$DB_PASSWORD"

psql   --host db   --port 5432   --username "$DB_USER"   --dbname "$DB_NAME"   --set=ON_ERROR_STOP=1   --set=runtime_user="$DB_RUNTIME_USER"   --set=runtime_password="$DB_RUNTIME_PASSWORD" <<'SQL'
SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION PASSWORD %L',
    :'runtime_user',
    :'runtime_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'runtime_user'
)
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION PASSWORD %L',
    :'runtime_user',
    :'runtime_password'
)
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'runtime_user')
\gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SELECT format('REVOKE CREATE ON SCHEMA public FROM %I', :'runtime_user')
\gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_user')
\gexec
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', :'runtime_user')
\gexec
SELECT format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO %I', :'runtime_user')
\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
    current_user,
    :'runtime_user'
)
\gexec
SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
    current_user,
    :'runtime_user'
)
\gexec

-- CRITICAL: Broad legacy DML grants above must never grant the application
-- access to privileged Data Center capture or operator audit tables.
-- Re-apply restrictions on EVERY deployment, including later pulls, for
-- whichever of these tables already exist at the current Alembic revision.
SELECT format('REVOKE ALL ON TABLE public.%I FROM %I', tablename, :'runtime_user')
FROM (VALUES
    ('loanhub_dc_capture'),
    ('loanhub_dc_clock'),
    ('loanhub_dc_event'),
    ('loanhub_dc_pilot_audit')
) AS protected(tablename)
WHERE to_regclass(format('public.%I', tablename)) IS NOT NULL
\gexec

-- Runtime can read only the three journal tables; RLS and API checks
-- additionally limit this SELECT permission by active tenant membership.
SELECT format('GRANT SELECT ON TABLE public.%I TO %I', tablename, :'runtime_user')
FROM (VALUES
    ('loanhub_dc_capture'),
    ('loanhub_dc_clock'),
    ('loanhub_dc_event')
) AS protected(tablename)
WHERE to_regclass(format('public.%I', tablename)) IS NOT NULL
\gexec

-- Fail closed rather than starting backend with a privileged runtime role.
SELECT 1 / (CASE WHEN EXISTS (
    SELECT 1 FROM (
        VALUES ('loanhub_dc_capture'),
               ('loanhub_dc_clock'),
               ('loanhub_dc_event'),
               ('loanhub_dc_pilot_audit')
    ) AS protected(tablename)
    WHERE to_regclass(format('public.%I', tablename)) IS NOT NULL
      AND (
        has_table_privilege(:'runtime_user', format('public.%I', tablename), 'INSERT')
        OR has_table_privilege(:'runtime_user', format('public.%I', tablename), 'UPDATE')
        OR has_table_privilege(:'runtime_user', format('public.%I', tablename), 'DELETE')
        OR (tablename = 'loanhub_dc_pilot_audit' AND
            has_table_privilege(:'runtime_user', format('public.%I', tablename), 'SELECT'))
      )
) THEN 0 ELSE 1 END) AS data_center_runtime_permission_guard;

-- The ordinary application login must NEVER be an issuer or stamp approver.
-- Explicitly override the broad legacy grants and default privileges above.
-- These tables are append-only or immutable in the official issuer design.
SELECT format(
    'REVOKE INSERT, UPDATE, DELETE ON TABLE %s FROM %I',
    string_agg(quote_ident(table_name), ', '),
    :'runtime_user'
)
FROM (
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN (
          'document_stamp_approvals',
          'document_stamp_approval_revocations',
          'document_issuances',
          'document_issuance_events'
      )
) restricted
HAVING count(*) > 0
\gexec

SELECT format(
    'ALTER ROLE %I SET search_path = public',
    :'runtime_user'
)
\gexec

SELECT
    rolname,
    rolsuper,
    rolcreatedb,
    rolcreaterole,
    rolreplication
FROM pg_roles
WHERE rolname = :'runtime_user';
SQL

echo "LoanHub runtime database role is present with DML-only schema access."
