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

if [[ ! -f .env ]]; then
    echo "Missing .env" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -f "$CHECKSUM_FILE" ]]; then
    sha256sum -c "$CHECKSUM_FILE"
else
    echo "WARNING: no checksum file found at $CHECKSUM_FILE" >&2
    echo "Run scripts/verify_backup.sh before any production restore." >&2
    exit 1
fi

# Parse the archive before any destructive action.
docker compose exec -T db     pg_restore     --list     < "$BACKUP_FILE"     > /dev/null

read -r -p "This will replace database objects in '$DB_NAME'. Type RESTORE: " confirmation

if [[ "$confirmation" != "RESTORE" ]]; then
    echo "Restore cancelled."
    exit 1
fi

docker compose exec -T db     pg_restore     --username "$DB_USER"     --dbname "$DB_NAME"     --clean     --if-exists     --exit-on-error     --no-owner     --no-privileges     < "$BACKUP_FILE"

echo "Restore completed successfully."
