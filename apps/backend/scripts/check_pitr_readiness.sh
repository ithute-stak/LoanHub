#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
    echo "Missing .env" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

ROW="$(
    docker compose exec -T db         psql         --username "$DB_USER"         --dbname "$DB_NAME"         --no-psqlrc         --tuples-only         --no-align         --field-separator='|'         --command "
            SELECT
                current_setting('wal_level'),
                current_setting('archive_mode'),
                current_setting('archive_command'),
                current_setting('max_wal_senders'),
                current_setting('synchronous_commit'),
                COALESCE(current_setting('wal_keep_size', true), ''),
                COALESCE(current_setting('data_checksums', true), ''),
                pg_is_in_recovery()::text,
                CASE
                    WHEN pg_is_in_recovery() THEN COALESCE(pg_last_wal_replay_lsn()::text, '')
                    ELSE pg_current_wal_lsn()::text
                END;
        "
)"

IFS='|' read -r WAL_LEVEL ARCHIVE_MODE ARCHIVE_COMMAND MAX_WAL_SENDERS SYNCHRONOUS_COMMIT WAL_KEEP_SIZE DATA_CHECKSUMS IS_RECOVERY CURRENT_LSN <<< "$ROW"

echo "PostgreSQL recovery readiness"
echo "database=$DB_NAME"
echo "wal_level=$WAL_LEVEL"
echo "archive_mode=$ARCHIVE_MODE"
echo "archive_command=$ARCHIVE_COMMAND"
echo "max_wal_senders=$MAX_WAL_SENDERS"
echo "synchronous_commit=$SYNCHRONOUS_COMMIT"
echo "wal_keep_size=$WAL_KEEP_SIZE"
echo "data_checksums=$DATA_CHECKSUMS"
echo "is_recovery=$IS_RECOVERY"
echo "current_or_replay_lsn=$CURRENT_LSN"

READY=true

if [[ "$WAL_LEVEL" == "minimal" ]]; then
    echo "NOT READY: wal_level=minimal cannot support continuous WAL archiving/replication." >&2
    READY=false
fi

if [[ "$ARCHIVE_MODE" != "on" && "$ARCHIVE_MODE" != "always" ]]; then
    echo "NOT READY: archive_mode is not enabled." >&2
    READY=false
fi

if [[ -z "$ARCHIVE_COMMAND" || "$ARCHIVE_COMMAND" == "(disabled)" ]]; then
    echo "NOT READY: archive_command is not configured." >&2
    READY=false
fi

if [[ "$READY" != "true" ]]; then
    echo "pitr_ready=false"
    exit 2
fi

echo "pitr_ready=true"
