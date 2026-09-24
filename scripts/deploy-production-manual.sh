#!/usr/bin/env bash
set -Eeuo pipefail

RELEASE_SHA="${1:-}"
APP_DIR="${LOANHUB_APP_DIR:-/opt/loanhub}"
BACKEND_IMAGE="ghcr.io/ithute-stak/loanhub-backend"
FRONTEND_IMAGE="ghcr.io/ithute-stak/loanhub-frontend"

if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: $0 <40-character-tested-release-sha>" >&2
  exit 2
fi

if [ "$APP_DIR" != "/opt/loanhub" ]; then
  echo "Refusing to operate outside /opt/loanhub." >&2
  exit 2
fi

cd "$APP_DIR"
test -f .env.production || { echo "Missing $APP_DIR/.env.production" >&2; exit 1; }
test -f compose.yaml || { echo "Missing $APP_DIR/compose.yaml" >&2; exit 1; }
test -f compose.edge.yml || { echo "Missing $APP_DIR/compose.edge.yml" >&2; exit 1; }
test -d secrets || { echo "Missing $APP_DIR/secrets" >&2; exit 1; }
test -f secrets/jwt_private.pem || { echo "Missing JWT private key" >&2; exit 1; }
test -f secrets/jwt_public.pem || { echo "Missing JWT public key" >&2; exit 1; }
docker network inspect public-edge >/dev/null 2>&1 || { echo "Missing Docker network: public-edge" >&2; exit 1; }

set -a
# shellcheck disable=SC1091
source .env.production
set +a

export LOANHUB_ENV_FILE=.env.production
export LOANHUB_BACKEND_IMAGE="$BACKEND_IMAGE"
export LOANHUB_FRONTEND_IMAGE="$FRONTEND_IMAGE"
export LOANHUB_IMAGE_TAG="$RELEASE_SHA"

compose=(docker compose --env-file .env.production -p loanhub -f compose.yaml -f compose.edge.yml)

wait_healthy() {
  local service="$1"
  local attempts="${2:-60}"
  local delay="${3:-3}"
  local container_id state
  container_id="$("${compose[@]}" ps -q "$service")"
  test -n "$container_id" || { echo "Missing container for $service" >&2; return 1; }
  state=""
  for _ in $(seq 1 "$attempts"); do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
    [ "$state" = "healthy" ] && return 0
    sleep "$delay"
  done
  echo "$service failed health verification: ${state:-unknown}" >&2
  "${compose[@]}" logs --tail=250 "$service" || true
  return 1
}

echo "[LoanHub] Pulling immutable release $RELEASE_SHA"
docker pull "$BACKEND_IMAGE:$RELEASE_SHA"
docker pull "$FRONTEND_IMAGE:$RELEASE_SHA"

docker image inspect "$BACKEND_IMAGE:$RELEASE_SHA" >/dev/null
docker image inspect "$FRONTEND_IMAGE:$RELEASE_SHA" >/dev/null

echo "[LoanHub] Starting persistent database and cache"
"${compose[@]}" up -d --no-build --pull never db redis
wait_healthy db 45 2

mkdir -p backups releases
previous_release=""
if [ -f releases/current.sha ]; then
  previous_release="$(tr -d '\r\n ' < releases/current.sha)"
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$APP_DIR/backups/loanhub-before-${RELEASE_SHA}-${timestamp}.dump"
echo "[LoanHub] Backing up PostgreSQL to $backup"
"${compose[@]}" exec -T db pg_dump --format=custom --no-owner --no-privileges -U "$DB_USER" "$DB_NAME" < /dev/null > "$backup"
test -s "$backup"

echo "[LoanHub] Applying Alembic migrations"
"${compose[@]}" up --no-build --pull never migrate

echo "[LoanHub] Starting tested application images"
"${compose[@]}" up -d --no-build --pull never db redis backend maintenance frontend
wait_healthy backend
wait_healthy frontend

echo "[LoanHub] Verifying public endpoints"
curl --retry 20 --retry-delay 3 --retry-all-errors -fsS https://api.loanhub.co.ls/health/ready >/dev/null
curl --retry 20 --retry-delay 3 --retry-all-errors -fsS https://loanhub.co.ls/ >/dev/null

if [ -n "$previous_release" ] && [ "$previous_release" != "$RELEASE_SHA" ]; then
  printf '%s\n' "$previous_release" > releases/previous.sha
fi
printf '%s\n' "$RELEASE_SHA" > releases/current.sha

"${compose[@]}" ps
printf '\n[LoanHub] Production is healthy on release %s\n' "$RELEASE_SHA"
printf '[LoanHub] Database backup: %s\n' "$backup"
if [ -n "$previous_release" ] && [ "$previous_release" != "$RELEASE_SHA" ]; then
  printf '[LoanHub] Previous release retained for rollback: %s\n' "$previous_release"
fi
