#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 backups/file.dump" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_FILE="$1"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

read -r -p "This will replace database objects in '$DB_NAME'. Type RESTORE: " confirmation

if [[ "$confirmation" != "RESTORE" ]]; then
    echo "Restore cancelled."
    exit 1
fi

docker compose exec -T db \
    pg_restore \
    --username "$DB_USER" \
    --dbname "$DB_NAME" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    < "$BACKUP_FILE"

echo "Restore completed."
