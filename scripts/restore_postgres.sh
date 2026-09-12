#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL must be set}"
backup="${1:?Usage: restore_postgres.sh BACKUP.dump}"

test -f "$backup"
if test -f "$backup.sha256"; then
  sha256sum --check "$backup.sha256"
fi

pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname="$RESTORE_DATABASE_URL" "$backup"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1;' >/dev/null
