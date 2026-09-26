#!/usr/bin/env bash
set -Eeuo pipefail

REQUESTED_RELEASE="${1:-}"
APP_DIR="${LOANHUB_APP_DIR:-/opt/loanhub}"
BACKEND_IMAGE="ghcr.io/ithute-stak/loanhub-backend"
FRONTEND_IMAGE="ghcr.io/ithute-stak/loanhub-frontend"
GITHUB_REPO_API="https://api.github.com/repos/ithute-stak/LoanHub"

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

mkdir -p backups releases
current_release=""
if [ -f releases/current.sha ]; then
  current_release="$(tr -d '\r\n ' < releases/current.sha)"
fi
if [ -n "$current_release" ] && [[ ! "$current_release" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid current production release marker: $current_release" >&2
  exit 1
fi

previous_retained_release=""
if [ -f releases/previous.sha ]; then
  previous_retained_release="$(tr -d '\r\n ' < releases/previous.sha)"
fi
if [ -n "$previous_retained_release" ] && [[ ! "$previous_retained_release" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid previous production release marker: $previous_retained_release" >&2
  exit 1
fi

api_get() {
  local url="$1"
  local -a headers=(
    -H 'Accept: application/vnd.github+json'
    -H 'X-GitHub-Api-Version: 2022-11-28'
    -H 'User-Agent: LoanHub-production-deployer'
  )
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    headers+=( -H "Authorization: Bearer $GITHUB_TOKEN" )
  fi
  curl -fsSL --retry 3 --retry-delay 2 "${headers[@]}" "$url"
}

compare_release() {
  local base="$1"
  local candidate="$2"
  api_get "$GITHUB_REPO_API/compare/${base}...${candidate}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", ""))'
}

resolve_latest_release() {
  if [ -z "$current_release" ]; then
    echo "Cannot auto-select latest without $APP_DIR/releases/current.sha. Deploy an exact tested SHA first." >&2
    return 1
  fi

  local runs_json candidate status
  runs_json="$(api_get "$GITHUB_REPO_API/actions/workflows/release-images.yml/runs?branch=main&status=success&per_page=50")"
  while IFS= read -r candidate; do
    [[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || continue
    if [ "$candidate" = "$current_release" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi

    status="$(compare_release "$current_release" "$candidate" || true)"
    [ "$status" = "ahead" ] || continue

    if docker manifest inspect "$BACKEND_IMAGE:$candidate" >/dev/null 2>&1 \
      && docker manifest inspect "$FRONTEND_IMAGE:$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(printf '%s' "$runs_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); [print(run.get("head_sha", "")) for run in data.get("workflow_runs", []) if run.get("conclusion") == "success" and run.get("head_branch") == "main"]')

  echo "No approved forward LoanHub release is available after $current_release." >&2
  return 1
}

case "$REQUESTED_RELEASE" in
  latest)
    echo "[LoanHub] Resolving latest approved forward production release..."
    RELEASE_SHA="$(resolve_latest_release)"
    ;;
  *)
    RELEASE_SHA="$REQUESTED_RELEASE"
    ;;
esac

if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: $0 <40-character-tested-release-sha|latest>" >&2
  exit 2
fi

if [ -n "$current_release" ]; then
  if [ "$RELEASE_SHA" = "$current_release" ]; then
    echo "[LoanHub] Production is already marked on $RELEASE_SHA. Verifying/reconciling the same release."
  else
    release_relation="$(compare_release "$current_release" "$RELEASE_SHA" || true)"
    if [ "$release_relation" != "ahead" ]; then
      echo "[LoanHub] REFUSING non-forward release $RELEASE_SHA from current $current_release (GitHub relation: ${release_relation:-unverified})." >&2
      echo "[LoanHub] Production rollback requires an explicit rollback/data-restore procedure; normal pull/deploy is forward-only." >&2
      exit 1
    fi
  fi
fi

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

verify_public_endpoints() {
  curl --retry 20 --retry-delay 3 --retry-all-errors -fsS https://api.loanhub.co.ls/health/ready >/dev/null
  curl --retry 20 --retry-delay 3 --retry-all-errors -fsS https://loanhub.co.ls/ >/dev/null
}

write_release_marker() {
  local path="$1"
  local value="$2"
  local temp="${path}.tmp.$$"
  printf '%s\n' "$value" > "$temp"
  mv -f "$temp" "$path"
}

ensure_rollback_image() {
  local image="$1"
  local release="$2"
  local service="$3"
  local expected_ref="${image}:${release}"
  local container_id running_ref image_id

  if docker image inspect "$expected_ref" >/dev/null 2>&1; then
    return 0
  fi

  container_id="$("${compose[@]}" ps -q "$service" 2>/dev/null || true)"
  if [ -n "$container_id" ]; then
    running_ref="$(docker inspect -f '{{.Config.Image}}' "$container_id" 2>/dev/null || true)"
    image_id="$(docker inspect -f '{{.Image}}' "$container_id" 2>/dev/null || true)"
    if [ "$running_ref" = "$expected_ref" ] && [ -n "$image_id" ]; then
      echo "[LoanHub] Preserving running $service image locally as rollback target $expected_ref"
      docker image tag "$image_id" "$expected_ref"
      docker image inspect "$expected_ref" >/dev/null
      return 0
    fi
  fi

  echo "[LoanHub] Pulling rollback image $expected_ref before production cutover"
  docker pull "$expected_ref"
  docker image inspect "$expected_ref" >/dev/null
}

prune_superseded_rollback_release() {
  local superseded="$1"
  local retained="$2"

  [ -n "$superseded" ] || return 0
  [ "$superseded" != "$retained" ] || return 0
  [ "$superseded" != "$RELEASE_SHA" ] || return 0

  echo "[LoanHub] Removing superseded local rollback image tags for $superseded"
  docker image rm "$BACKEND_IMAGE:$superseded" >/dev/null 2>&1 || true
  docker image rm "$FRONTEND_IMAGE:$superseded" >/dev/null 2>&1 || true
}

rollback_armed=0
rollback_release=""
deployment_phase="preflight"

handle_deployment_failure() {
  local status="${1:-1}"
  local location="${2:-unknown}"
  local rollback_ok=1

  trap - ERR HUP INT TERM
  set +e

  echo "[LoanHub] DEPLOYMENT FAILED during ${deployment_phase} (status=$status, location=$location)." >&2

  if [ "$rollback_armed" -ne 1 ] || [ -z "$rollback_release" ]; then
    echo "[LoanHub] Existing production containers were not replaced or no rollback release is available." >&2
    exit "$status"
  fi

  rollback_armed=0
  write_release_marker releases/last-failed.sha "$RELEASE_SHA" || true
  rm -f releases/deploying.sha

  echo "[LoanHub] Automatic application rollback starting: $RELEASE_SHA -> $rollback_release" >&2
  export LOANHUB_IMAGE_TAG="$rollback_release"

  "${compose[@]}" up -d --no-build --pull never --no-deps backend || rollback_ok=0
  if [ "$rollback_ok" -eq 1 ]; then
    wait_healthy backend 60 3 || rollback_ok=0
  fi

  "${compose[@]}" up -d --no-build --pull never --no-deps maintenance frontend || rollback_ok=0
  if [ "$rollback_ok" -eq 1 ]; then
    wait_healthy frontend 60 3 || rollback_ok=0
  fi

  if [ "$rollback_ok" -eq 1 ]; then
    verify_public_endpoints || rollback_ok=0
  fi

  if [ "$rollback_ok" -eq 1 ]; then
    write_release_marker releases/current.sha "$rollback_release" || rollback_ok=0
  fi

  if [ "$rollback_ok" -eq 1 ]; then
    echo "[LoanHub] Automatic application rollback succeeded. Production remains on $rollback_release." >&2
  else
    echo "[LoanHub] CRITICAL: automatic rollback could not restore a healthy application release." >&2
    echo "[LoanHub] Database backup remains available at: ${backup:-not-created}" >&2
    echo "[LoanHub] Do not restore the database automatically; inspect migration compatibility and service logs first." >&2
  fi

  export LOANHUB_IMAGE_TAG="$RELEASE_SHA"
  exit "$status"
}

handle_deployment_signal() {
  local signal_name="$1"
  local status="$2"
  handle_deployment_failure "$status" "signal:${signal_name}"
}

echo "[LoanHub] Pulling immutable release $RELEASE_SHA"
docker pull "$BACKEND_IMAGE:$RELEASE_SHA"
docker pull "$FRONTEND_IMAGE:$RELEASE_SHA"

docker image inspect "$BACKEND_IMAGE:$RELEASE_SHA" >/dev/null
docker image inspect "$FRONTEND_IMAGE:$RELEASE_SHA" >/dev/null

if [ -n "$current_release" ] && [ "$current_release" != "$RELEASE_SHA" ]; then
  echo "[LoanHub] Securing current release $current_release locally for automatic rollback"
  ensure_rollback_image "$BACKEND_IMAGE" "$current_release" backend
  ensure_rollback_image "$FRONTEND_IMAGE" "$current_release" frontend
  rollback_release="$current_release"
fi

echo "[LoanHub] Starting persistent database and cache"
"${compose[@]}" up -d --no-build --pull never db redis
wait_healthy db 45 2

echo "[LoanHub] Running candidate backend import smoke before database migration or application cutover"
"${compose[@]}" run --rm --no-deps backend python -c 'import main; print("LoanHub backend import smoke passed")'

alembic_table=""
if ! alembic_table="$(
  "${compose[@]}" exec -T db psql -Atq -U "$DB_USER" "$DB_NAME" \
    -c "SELECT COALESCE(to_regclass('public.alembic_version')::text, '')" < /dev/null
)"; then
  echo "[LoanHub] Unable to inspect the live Alembic version table; refusing deployment." >&2
  exit 1
fi
alembic_table="$(printf '%s' "$alembic_table" | tr -d '\r\n ')"

db_revisions=()
if [ "$alembic_table" = "alembic_version" ]; then
  db_revision_output=""
  if ! db_revision_output="$(
    "${compose[@]}" exec -T db psql -Atq -U "$DB_USER" "$DB_NAME" \
      -c "SELECT version_num FROM alembic_version ORDER BY version_num" < /dev/null
  )"; then
    echo "[LoanHub] Unable to read the live Alembic revisions; refusing deployment." >&2
    exit 1
  fi
  mapfile -t db_revisions < <(printf '%s\n' "$db_revision_output" | sed '/^[[:space:]]*$/d')
fi

for db_revision in "${db_revisions[@]}"; do
  [ -n "$db_revision" ] || continue
  echo "[LoanHub] Verifying candidate contains current Alembic revision $db_revision"
  docker run --rm \
    --entrypoint python \
    -e "LOANHUB_REQUIRED_ALEMBIC_REVISION=$db_revision" \
    "$BACKEND_IMAGE:$RELEASE_SHA" \
    -c 'import os,pathlib,re,sys; rev=os.environ["LOANHUB_REQUIRED_ALEMBIC_REVISION"]; pattern=re.compile(r"(?m)^revision(?:\\s*:[^=]+)?\\s*=\\s*[\"\x27]"+re.escape(rev)+r"[\"\x27]"); files=pathlib.Path("/app/alembic/versions").glob("*.py"); sys.exit(0 if any(pattern.search(p.read_text(encoding="utf-8")) for p in files) else 42)' \
    || {
      echo "[LoanHub] REFUSING release $RELEASE_SHA: its migration history does not contain live database revision $db_revision." >&2
      echo "[LoanHub] This is normally a stale/older release. The database was not migrated and application containers were not replaced." >&2
      exit 1
    }
done

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$APP_DIR/backups/loanhub-before-${RELEASE_SHA}-${timestamp}.dump"
echo "[LoanHub] Backing up PostgreSQL to $backup"
"${compose[@]}" exec -T db pg_dump --format=custom --no-owner --no-privileges -U "$DB_USER" "$DB_NAME" < /dev/null > "$backup"
test -s "$backup"

echo "[LoanHub] Applying Alembic migrations (fail-closed)"
"${compose[@]}" run --rm --no-deps migrate

if [ -n "$rollback_release" ]; then
  echo "[LoanHub] Arming automatic application rollback to $rollback_release"
  write_release_marker releases/deploying.sha "$RELEASE_SHA"
  rollback_armed=1
  trap 'handle_deployment_failure "$?" "$LINENO"' ERR
  trap 'handle_deployment_signal HUP 129' HUP
  trap 'handle_deployment_signal INT 130' INT
  trap 'handle_deployment_signal TERM 143' TERM
fi

deployment_phase="backend cutover"
echo "[LoanHub] Starting tested backend image"
"${compose[@]}" up -d --no-build --pull never --no-deps backend
wait_healthy backend

deployment_phase="frontend and maintenance cutover"
"${compose[@]}" up -d --no-build --pull never --no-deps maintenance frontend
wait_healthy frontend

deployment_phase="public endpoint verification"
echo "[LoanHub] Verifying public endpoints"
verify_public_endpoints

deployment_phase="release commit"
if [ -n "$current_release" ] && [ "$current_release" != "$RELEASE_SHA" ]; then
  write_release_marker releases/previous.sha "$current_release"
fi
write_release_marker releases/current.sha "$RELEASE_SHA"
rm -f releases/deploying.sha
rollback_armed=0
trap - ERR HUP INT TERM

if [ -n "$current_release" ] && [ "$current_release" != "$RELEASE_SHA" ]; then
  prune_superseded_rollback_release "$previous_retained_release" "$current_release"
fi

"${compose[@]}" ps
printf '\n[LoanHub] Production is healthy on release %s\n' "$RELEASE_SHA"
printf '[LoanHub] Database backup: %s\n' "$backup"
if [ -n "$current_release" ] && [ "$current_release" != "$RELEASE_SHA" ]; then
  printf '[LoanHub] Previous release retained locally and recorded for rollback: %s\n' "$current_release"
fi
