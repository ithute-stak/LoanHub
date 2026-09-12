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

mkdir -p backups
chmod 700 backups

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="backups/loanhub_${TIMESTAMP}.dump"

docker compose exec -T db \
    pg_dump \
    --username "$DB_USER" \
    --dbname "$DB_NAME" \
    --format custom \
    --no-owner \
    --no-privileges \
    > "$OUTPUT"

chmod 600 "$OUTPUT"
echo "Database backup created: $OUTPUT"
