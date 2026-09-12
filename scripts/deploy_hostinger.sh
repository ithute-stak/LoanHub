#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${LOANHUB_PRODUCTION_ENV_FILE:-.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[LoanHub] Missing $ENV_FILE. Run: bash ./scripts/prepare_production_env.sh <email>"
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

LOANHUB_PRODUCTION_ENV_FILE="$ENV_FILE" bash ./scripts/production_preflight.sh

export LOANHUB_ENV_FILE="${LOANHUB_ENV_FILE:-$ENV_FILE}"
export LOANHUB_BACKEND_IMAGE="${LOANHUB_BACKEND_IMAGE:-ghcr.io/lelefe-dc/loanhub-backend}"
export LOANHUB_FRONTEND_IMAGE="${LOANHUB_FRONTEND_IMAGE:-ghcr.io/lelefe-dc/loanhub-frontend}"
export LOANHUB_IMAGE_TAG="${LOANHUB_IMAGE_TAG:-latest}"

COMPOSE=(docker compose --env-file "$ENV_FILE" --profile production)

if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
    echo "[LoanHub] Logging in to GitHub Container Registry"
    printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
fi

mkdir -p backups

pull_service() {
    local service="$1"
    local attempt
    for attempt in 1 2 3 4 5; do
        if "${COMPOSE[@]}" pull "$service"; then
            return 0
        fi
        if [[ "$attempt" -lt 5 ]]; then
            echo "[LoanHub] Pull for $service failed ($attempt/5); retrying in 10 seconds..." >&2
            sleep 10
        fi
    done
    echo "[LoanHub] Unable to pull $service after 5 attempts" >&2
    return 1
}

echo "[LoanHub] Pulling database, cache, proxy and published application images"
for service in db redis caddy backend frontend; do
    pull_service "$service"
done

# Start only stateful dependencies first so the database can be backed up before
# any application migration changes its schema.
"${COMPOSE[@]}" up -d --no-build --pull never db redis

DB_ID="$("${COMPOSE[@]}" ps -q db)"
DB_HEALTH=""
for attempt in $(seq 1 40); do
    DB_HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$DB_ID" 2>/dev/null || true)"
    if [[ "$DB_HEALTH" == "healthy" ]]; then
        break
    fi
    sleep 2
done
if [[ "$DB_HEALTH" != "healthy" ]]; then
    echo "[LoanHub] PostgreSQL failed health verification: ${DB_HEALTH:-unknown}" >&2
    "${COMPOSE[@]}" logs --tail=200 db
    exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="backups/loanhub-before-${timestamp}.dump"
echo "[LoanHub] Creating PostgreSQL backup: $backup"
"${COMPOSE[@]}" exec -T db pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    -U "$DB_USER" \
    "$DB_NAME" > "$backup"
test -s "$backup"

echo "[LoanHub] Applying the Alembic migration chain with the published backend image"
"${COMPOSE[@]}" up --no-build --pull never migrate

echo "[LoanHub] Starting LoanHub with Dockerized PostgreSQL, Redis and Caddy"
"${COMPOSE[@]}" up -d --no-build --pull never --remove-orphans

echo "[LoanHub] Waiting for HTTPS frontend and API health"
healthy=false
for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error --max-time 5 \
        "https://${APP_DOMAIN}/" >/dev/null 2>&1 \
        && curl --fail --silent --show-error --max-time 5 \
        "https://${API_DOMAIN}/health/ready" >/dev/null 2>&1; then
        healthy=true
        break
    fi
    sleep 5
done

"${COMPOSE[@]}" ps

if [[ "$healthy" != true ]]; then
    echo "[LoanHub] Deployment did not become healthy within 5 minutes."
    echo "[LoanHub] Check DNS, firewall and Caddy logs:"
    echo "  docker compose --env-file $ENV_FILE --profile production logs --tail=200 caddy backend frontend"
    exit 1
fi

echo "[LoanHub] Deployment is healthy"
echo "[LoanHub] Release:  ${LOANHUB_IMAGE_TAG}"
echo "[LoanHub] Frontend: https://${APP_DOMAIN}"
echo "[LoanHub] API:      https://${API_DOMAIN}"
docker image prune -f
