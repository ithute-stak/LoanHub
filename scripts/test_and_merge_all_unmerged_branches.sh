#!/usr/bin/env bash
set -Eeuo pipefail

REMOTE="${REMOTE:-origin}"
PUSH_MAIN="${PUSH_MAIN:-0}"
ALLOW_PARTIAL="${ALLOW_PARTIAL:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
PG_PORT="${PG_PORT:-55432}"
REDIS_PORT="${REDIS_PORT:-56379}"
API_PORT="${API_PORT:-18000}"
WEB_PORT="${WEB_PORT:-13000}"
PG_CONTAINER="${PG_CONTAINER:-loanhub-branch-gate-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-loanhub-branch-gate-redis}"
TOOLING_BRANCH="tooling/local-all-branches-quality-gate"

ORIGINAL_ROOT="$(git rev-parse --show-toplevel)"
STAMP="$(date +%Y%m%d-%H%M%S)"
STATE_DIR="$(mktemp -d -t loanhub-branch-gate-XXXXXX)"
WORKTREE="$STATE_DIR/worktree"
VENV_DIR="$STATE_DIR/venv"
REPORT_PATH="${REPORT_PATH:-$ORIGINAL_ROOT/branch-gate-results-$STAMP.txt}"
JWT_PRIVATE_KEY_PATH="$STATE_DIR/jwt-private.pem"
JWT_PUBLIC_KEY_PATH="$STATE_DIR/jwt-public.pem"
API_PID=""
WEB_PID=""
PNPM=""

log() {
  printf '%s\n' "$*" | tee -a "$REPORT_PATH"
}

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'ERROR: required command %s was not found.\n' "$1" >&2
    exit 2
  fi
}

stop_apps() {
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "$WEB_PID" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
  if [[ -n "$API_PID" ]]; then wait "$API_PID" 2>/dev/null || true; fi
  if [[ -n "$WEB_PID" ]]; then wait "$WEB_PID" 2>/dev/null || true; fi
  API_PID=""
  WEB_PID=""
}

cleanup() {
  stop_apps
  docker rm -f "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  if git -C "$ORIGINAL_ROOT" worktree list --porcelain | grep -Fqx "worktree $WORKTREE"; then
    git -C "$ORIGINAL_ROOT" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  fi
  rm -rf "$STATE_DIR"
}
trap cleanup EXIT INT TERM

for cmd in git docker curl psql pg_dump pg_restore openssl; do
  require "$cmd"
done

if command -v pnpm >/dev/null 2>&1; then
  PNPM="pnpm"
elif command -v corepack >/dev/null 2>&1; then
  corepack prepare pnpm@10 --activate
  PNPM="pnpm"
else
  printf 'ERROR: pnpm or corepack is required.\n' >&2
  exit 2
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    printf 'ERROR: Python was not found. Set PYTHON_BIN to Python 3.13.\n' >&2
    exit 2
  fi
fi

: > "$REPORT_PATH"
log "LoanHub all-branches local quality gate"
log "Started: $(date -Is)"
log "Repository: $ORIGINAL_ROOT"
log "Remote: $REMOTE"
log "Push main after validation: $PUSH_MAIN"
log "Allow partial push: $ALLOW_PARTIAL"

cd "$ORIGINAL_ROOT"
git fetch "$REMOTE" --prune
START_MAIN_SHA="$(git rev-parse "$REMOTE/main")"
log "Starting remote main: $START_MAIN_SHA"

git worktree add --detach "$WORKTREE" "$START_MAIN_SHA" >/dev/null
cd "$WORKTREE"

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
  -out "$JWT_PRIVATE_KEY_PATH" >/dev/null 2>&1
openssl pkey -in "$JWT_PRIVATE_KEY_PATH" -pubout \
  -out "$JWT_PUBLIC_KEY_PATH" >/dev/null 2>&1

docker rm -f "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_DB=loan_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p "127.0.0.1:${PG_PORT}:5432" \
  postgres:16-alpine >/dev/null
docker run -d --name "$REDIS_CONTAINER" \
  -p "127.0.0.1:${REDIS_PORT}:6379" \
  redis:7-alpine >/dev/null

for _ in $(seq 1 60); do
  docker exec "$PG_CONTAINER" pg_isready -U postgres -d loan_db >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$PG_CONTAINER" pg_isready -U postgres -d loan_db >/dev/null
for _ in $(seq 1 30); do
  docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q PONG && break
  sleep 1
done
docker exec "$REDIS_CONTAINER" redis-cli ping | grep -q PONG

export SECRET_KEY="local-branch-gate-secret-key"
export FERNET_SECRET_KEY="ci-only-fernet-key-not-for-production"
export JWT_PRIVATE_KEY_PATH
export JWT_PUBLIC_KEY_PATH
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@127.0.0.1:${PG_PORT}/loan_db"
export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
export CORS_ORIGINS="http://127.0.0.1:${WEB_PORT}"
export AUTH_RATE_LIMIT="5/minute"
export TREASURY_AUTO_SUBMIT_ENABLED="false"
export MIDNIGHT_REPORTS_ENABLED="false"
export COLLECTION_DAILY_REPORT_ENABLED="false"
export NEXT_PUBLIC_API_URL="http://127.0.0.1:${API_PORT}/api/v1"
export LOANHUB_WEB_BASE_URL="http://127.0.0.1:${WEB_PORT}"
export LOANHUB_API_BASE_URL="http://127.0.0.1:${API_PORT}"
export LOANHUB_E2E_PHONE="59000000"
export LOANHUB_E2E_PASSWORD="Local-LoanHub-E2E-Password-2026!"

reset_database() {
  stop_apps
  docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS loan_db WITH (FORCE);" >/dev/null
  docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE loan_db;" >/dev/null
  docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS loan_db_drill WITH (FORCE);" >/dev/null
  docker exec "$REDIS_CONTAINER" redis-cli FLUSHALL >/dev/null
}

run_quality_gate() {
  local branch="$1"
  local safe_tag
  safe_tag="$(printf '%s' "$branch" | tr '/:@ ' '----' | tr -cd '[:alnum:]_.-')"

  log "  Installing backend dependencies"
  python -m pip install -r apps/backend/requirements.txt -r apps/backend/requirements-dev.txt

  log "  Repository secret scan"
  python scripts/secret_scan.py

  log "  Bandit SAST"
  python -m bandit -r apps/backend -x apps/backend/tests -lll

  reset_database

  log "  Backend compile + complete pytest"
  (
    cd apps/backend
    python -m compileall -q .
    python -m pytest -q
  )

  reset_database

  log "  Alembic single-head + PostgreSQL upgrade"
  (
    cd apps/backend
    test "$(python -m alembic heads | grep -c '(head)')" -eq 1
    python -m alembic upgrade head
    python -m alembic current
  )

  log "  Double-entry accounting integrity"
  python scripts/accounting_integrity_check.py

  log "  PostgreSQL backup/restore drill"
  docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE loan_db_drill;" >/dev/null
  DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${PG_PORT}/loan_db" \
  DRILL_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${PG_PORT}/loan_db_drill" \
    bash ./scripts/drill_backup_restore.sh
  docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE loan_db_drill WITH (FORCE);" >/dev/null

  log "  Frontend install + typecheck + lint + build"
  "$PNPM" --dir apps/frontend install --frozen-lockfile
  "$PNPM" --dir apps/frontend typecheck
  "$PNPM" --dir apps/frontend lint
  NEXT_PUBLIC_API_URL=/api/v1 "$PNPM" --dir apps/frontend build

  log "  Browser E2E + DAST"
  python -m playwright install --with-deps chromium
  python apps/backend/scripts/create_superadmin.py \
    --phone "$LOANHUB_E2E_PHONE" \
    --email local-branch-gate-owner@example.com \
    --first-name Local \
    --last-name Gate \
    --password "$LOANHUB_E2E_PASSWORD"

  (
    cd apps/backend
    python -m uvicorn main:app --host 127.0.0.1 --port "$API_PORT" \
      >"$STATE_DIR/api.log" 2>&1 &
    echo $! >"$STATE_DIR/api.pid"
  )
  API_PID="$(cat "$STATE_DIR/api.pid")"

  (
    cd apps/frontend
    NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
      "$PNPM" dev --hostname 127.0.0.1 --port "$WEB_PORT" \
      >"$STATE_DIR/web.log" 2>&1 &
    echo $! >"$STATE_DIR/web.pid"
  )
  WEB_PID="$(cat "$STATE_DIR/web.pid")"

  local ready=0
  for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:${API_PORT}/health/ready" >/dev/null 2>&1 \
      && curl -fsS "http://127.0.0.1:${WEB_PORT}/login" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    cat "$STATE_DIR/api.log" >&2 || true
    cat "$STATE_DIR/web.log" >&2 || true
    return 1
  fi

  python -m pytest -q apps/backend/tests/e2e/test_browser_lending_journey.py
  python scripts/dast_smoke.py
  stop_apps

  log "  Docker Compose validation + production image build"
  cp .env.example .env
  docker compose config >/dev/null
  rm -f .env
  docker build --pull --progress=plain \
    --build-arg NEXT_PUBLIC_API_URL=/api/v1 \
    --build-arg "APP_VERSION=$(git rev-parse HEAD)" \
    --tag "loanhub-branch-gate:${safe_tag}" \
    .
}

mapfile -t BRANCHES < <(
  while IFS= read -r ref; do
    branch="${ref#refs/remotes/$REMOTE/}"
    if [[ "$branch" == "HEAD" || "$branch" == "main" || "$branch" == "$TOOLING_BRANCH" ]]; then
      continue
    fi
    timestamp="$(git log -1 --format=%ct "$ref")"
    priority=0
    [[ "$branch" == dependabot/* ]] && priority=1
    printf '%s %s %s\n' "$priority" "$timestamp" "$branch"
  done < <(git for-each-ref --format='%(refname)' "refs/remotes/$REMOTE/") \
    | sort -n -k1,1 -k2,2 \
    | awk '{print $3}'
)

ACCEPTED_SHA="$START_MAIN_SHA"
PASS_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0
CONFLICT_COUNT=0

for branch in "${BRANCHES[@]}"; do
  remote_ref="$REMOTE/$branch"

  if git merge-base --is-ancestor "$remote_ref" "$ACCEPTED_SHA"; then
    log "SKIP already contained: $branch"
    ((SKIP_COUNT+=1))
    continue
  fi

  log ""
  log "CANDIDATE: $branch"
  git checkout --detach "$ACCEPTED_SHA" >/dev/null
  rm -f .env

  if ! git merge --no-ff --no-edit "$remote_ref"; then
    git merge --abort >/dev/null 2>&1 || true
    git reset --hard "$ACCEPTED_SHA" >/dev/null
    rm -f .env
    log "CONFLICT: $branch"
    ((CONFLICT_COUNT+=1))
    continue
  fi

  if run_quality_gate "$branch"; then
    ACCEPTED_SHA="$(git rev-parse HEAD)"
    log "PASS + ACCEPTED: $branch -> $ACCEPTED_SHA"
    ((PASS_COUNT+=1))
  else
    stop_apps
    git reset --hard "$ACCEPTED_SHA" >/dev/null
    rm -f .env
    log "FAIL: $branch (not accepted)"
    ((FAIL_COUNT+=1))
  fi
done

log ""
log "Summary: passed=$PASS_COUNT already-contained=$SKIP_COUNT conflicts=$CONFLICT_COUNT failed=$FAIL_COUNT"
log "Starting main: $START_MAIN_SHA"
log "Validated aggregate: $ACCEPTED_SHA"

if [[ "$ACCEPTED_SHA" != "$START_MAIN_SHA" ]]; then
  if (( CONFLICT_COUNT > 0 || FAIL_COUNT > 0 )) && [[ "$ALLOW_PARTIAL" != "1" ]]; then
    log "Not pushed because one or more branches conflicted or failed. Resolve them, then rerun."
    log "Set ALLOW_PARTIAL=1 only if you intentionally want the passing subset pushed."
  elif [[ "$PUSH_MAIN" == "1" ]]; then
    log "Pushing validated aggregate to $REMOTE/main"
    git push "$REMOTE" "$ACCEPTED_SHA:refs/heads/main"
    log "PUSHED: $ACCEPTED_SHA -> $REMOTE/main"
  else
    log "Not pushed. Re-run with PUSH_MAIN=1 to update remote main after validation."
  fi
else
  log "No new branch passed validation; main was not changed."
fi

log "Report: $REPORT_PATH"
log "Finished: $(date -Is)"
