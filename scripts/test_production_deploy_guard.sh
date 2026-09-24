#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="$ROOT_DIR/scripts/deploy-production-manual.sh"

bash -n "$DEPLOY_SCRIPT"
python3 "$ROOT_DIR/scripts/check_production_deploy_guard.py"

grep -Fq 'compare/${base}...${candidate}' "$DEPLOY_SCRIPT"
grep -Fq 'status=success&per_page=50' "$DEPLOY_SCRIPT"
grep -Fq 'REFUSING non-forward release' "$DEPLOY_SCRIPT"
grep -Fq 'migration history does not contain live database revision' "$DEPLOY_SCRIPT"
grep -Fq 'run --rm --no-deps migrate' "$DEPLOY_SCRIPT"
grep -Fq 'up -d --no-build --pull never --no-deps backend' "$DEPLOY_SCRIPT"

printf 'Production deployment guard checks passed.\n'
