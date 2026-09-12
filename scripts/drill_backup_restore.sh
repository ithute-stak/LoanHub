#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${DRILL_DATABASE_URL:?DRILL_DATABASE_URL must be set}"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
export BACKUP_DIR="$workdir"
backup="$(bash ./scripts/backup_postgres.sh)"
RESTORE_DATABASE_URL="$DRILL_DATABASE_URL" bash ./scripts/restore_postgres.sh "$backup"

source_head="$(psql "$DATABASE_URL" -Atc 'SELECT version_num FROM alembic_version LIMIT 1')"
drill_head="$(psql "$DRILL_DATABASE_URL" -Atc 'SELECT version_num FROM alembic_version LIMIT 1')"
test -n "$source_head"
test "$source_head" = "$drill_head"

printf 'Disaster-recovery drill passed at Alembic head %s\n' "$drill_head"
