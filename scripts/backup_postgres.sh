#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_DIR/loanhub-${timestamp}.dump"
checksum="$backup.sha256"

pg_dump --format=custom --compress=9 --no-owner --no-privileges --dbname="$DATABASE_URL" --file="$backup"
sha256sum "$backup" > "$checksum"
find "$BACKUP_DIR" -type f \( -name 'loanhub-*.dump' -o -name 'loanhub-*.dump.sha256' \) -mtime "+$RETENTION_DAYS" -delete
printf '%s\n' "$backup"
