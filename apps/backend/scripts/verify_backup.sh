#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 backups/file.dump" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_FILE="$1"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

if [[ ! -f "$CHECKSUM_FILE" ]]; then
    echo "Checksum file not found: $CHECKSUM_FILE" >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Missing .env" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

sha256sum -c "$CHECKSUM_FILE"

# Confirm PostgreSQL can parse the custom archive before creating a drill DB.
docker compose exec -T db     pg_restore     --list     < "$BACKUP_FILE"     > /dev/null

SAFE_TS="$(date -u +%Y%m%d%H%M%S)"
VERIFY_DB="loanhub_restore_verify_${SAFE_TS}_$$"

cleanup() {
    docker compose exec -T db         dropdb         --username "$DB_USER"         --if-exists         "$VERIFY_DB"         >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose exec -T db     createdb     --username "$DB_USER"     "$VERIFY_DB"

docker compose exec -T db     pg_restore     --username "$DB_USER"     --dbname "$VERIFY_DB"     --exit-on-error     --no-owner     --no-privileges     < "$BACKUP_FILE"

docker compose exec -T db     psql     --username "$DB_USER"     --dbname "$VERIFY_DB"     --no-psqlrc     --tuples-only     --command "SELECT 1"     >/dev/null

ALEMBIC_HEADS="$(
    docker compose exec -T db         psql         --username "$DB_USER"         --dbname "$VERIFY_DB"         --no-psqlrc         --tuples-only         --no-align         --command "SELECT version_num FROM alembic_version ORDER BY version_num"         | tr '\n' ',' | sed 's/,$//'
)"

if [[ -z "$ALEMBIC_HEADS" ]]; then
    echo "Restore verification failed: alembic_version is empty" >&2
    exit 1
fi

echo "Restore verification passed."
echo "Temporary database: $VERIFY_DB"
echo "Recovered Alembic head(s): $ALEMBIC_HEADS"
