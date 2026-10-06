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
CHECKSUM="${OUTPUT}.sha256"
METADATA="${OUTPUT}.meta"

docker compose exec -T db     pg_dump     --username "$DB_USER"     --dbname "$DB_NAME"     --format custom     --no-owner     --no-privileges     > "$OUTPUT"

chmod 600 "$OUTPUT"

# A successful pg_dump process is not enough evidence that the artifact is
# readable. Parse the custom archive immediately before calling it a backup.
docker compose exec -T db     pg_restore     --list     < "$OUTPUT"     > /dev/null

sha256sum "$OUTPUT" > "$CHECKSUM"
chmod 600 "$CHECKSUM"

BACKUP_BYTES="$(wc -c < "$OUTPUT" | tr -d ' ')"
BACKUP_SHA256="$(cut -d' ' -f1 "$CHECKSUM")"
cat > "$METADATA" <<EOF
created_at_utc=${TIMESTAMP}
database=${DB_NAME}
format=postgresql_custom
bytes=${BACKUP_BYTES}
sha256=${BACKUP_SHA256}
verified_archive_list=true
EOF
chmod 600 "$METADATA"

echo "Database backup created and archive-verified: $OUTPUT"
echo "Checksum: $CHECKSUM"
echo "Metadata: $METADATA"
