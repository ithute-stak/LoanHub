#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

HEAD="$(alembic heads | awk 'NR == 1 {print $1}')"

if [[ -z "$HEAD" ]]; then
    echo "Could not determine the Alembic head." >&2
    exit 1
fi

UPGRADE_SQL="$(mktemp)"
DOWNGRADE_SQL="$(mktemp)"
trap 'rm -f "$UPGRADE_SQL" "$DOWNGRADE_SQL"' EXIT

alembic upgrade head --sql > "$UPGRADE_SQL"
alembic downgrade "${HEAD}:base" --sql > "$DOWNGRADE_SQL"

test -s "$UPGRADE_SQL"
test -s "$DOWNGRADE_SQL"

echo "Offline Alembic validation passed."
echo "Head: $HEAD"
echo "Upgrade SQL lines: $(wc -l < "$UPGRADE_SQL")"
echo "Downgrade SQL lines: $(wc -l < "$DOWNGRADE_SQL")"
