#!/usr/bin/env sh
set -eu
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/$STAMP"
mkdir -p "$BACKUP_DIR"

DB_USER_VALUE=${DB_USER:-loanhub}
DB_NAME_VALUE=${DB_NAME:-loan_db}

# Read values from .env without executing it.
if [ -f .env ]; then
    DB_USER_VALUE=$(sed -n 's/^DB_USER=//p' .env | tail -1)
    DB_NAME_VALUE=$(sed -n 's/^DB_NAME=//p' .env | tail -1)
fi

docker compose exec -T db pg_dump -U "$DB_USER_VALUE" -d "$DB_NAME_VALUE" -Fc > "$BACKUP_DIR/database.dump"
docker run --rm \
    -v "${COMPOSE_PROJECT_NAME:-loanhub}_loanhub_files:/source:ro" \
    -v "$ROOT_DIR/$BACKUP_DIR:/backup" \
    alpine:3.21 sh -c 'cd /source && tar -czf /backup/files.tar.gz .'

printf 'Backup created: %s\n' "$BACKUP_DIR"
