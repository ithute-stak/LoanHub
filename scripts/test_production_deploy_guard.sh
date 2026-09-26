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
grep -Fq 'Running candidate backend import smoke before database migration or application cutover' "$DEPLOY_SCRIPT"
grep -Fq 'Securing current release $current_release locally for automatic rollback' "$DEPLOY_SCRIPT"
grep -Fq 'rollback_armed=1' "$DEPLOY_SCRIPT"
grep -Fq 'releases/deploying.sha' "$DEPLOY_SCRIPT"
grep -Fq 'releases/last-failed.sha' "$DEPLOY_SCRIPT"
grep -Fq 'export LOANHUB_IMAGE_TAG="$rollback_release"' "$DEPLOY_SCRIPT"
grep -Fq 'Automatic application rollback succeeded' "$DEPLOY_SCRIPT"
grep -Fq "trap 'handle_deployment_signal HUP 129' HUP" "$DEPLOY_SCRIPT"
grep -Fq 'write_release_marker releases/current.sha "$RELEASE_SHA"' "$DEPLOY_SCRIPT"

printf 'Production deployment guard checks passed.\n'
