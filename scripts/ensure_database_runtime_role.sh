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
