#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/backend"
FRONTEND_DIR="$ROOT_DIR/apps/frontend"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AUTO_INSTALL="${LOANHUB_AUTO_INSTALL:-1}"
RUN_MIGRATIONS="${LOANHUB_RUN_MIGRATIONS:-1}"

BACKEND_PID=""
FRONTEND_PID=""
PYTHON_BIN=""
PNPM_CMD=()

usage() {
  cat <<USAGE
LoanHub local launcher

Usage:
  ./start.sh             Apply database migrations, then start FastAPI and Next.js together
  ./start.sh --check     Validate local prerequisites without starting or changing the database
  ./start.sh --docker    Start the existing Docker Compose stack
  ./start.sh --help      Show this help

Environment overrides:
  BACKEND_HOST             FastAPI bind host (default: 0.0.0.0)
  BACKEND_PORT             FastAPI port (default: 8000)
  FRONTEND_HOST            Next.js bind host (default: 0.0.0.0)
  FRONTEND_PORT            Next.js port (default: 3000)
  LOANHUB_AUTO_INSTALL     1 installs/synchronizes local dependencies; 0 only checks
  LOANHUB_RUN_MIGRATIONS   1 runs 'alembic upgrade head' before local startup; 0 skips it

Local URLs:
  Frontend: http://localhost:${FRONTEND_PORT}
  Backend:  http://localhost:${BACKEND_PORT}
  API docs: http://localhost:${BACKEND_PORT}/docs
USAGE
}

fail() {
  printf 'LoanHub startup error: %s\n' "$*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

port_is_busy() {
  local port="$1"
  if command_exists ss; then
    ss -ltn "sport = :${port}" 2>/dev/null | grep -q LISTEN
    return $?
  fi
  return 1
}

choose_python() {
  if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
    return
  fi
  if [[ -x "$BACKEND_DIR/venv/bin/python" ]]; then
    PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
    return
  fi
  if command_exists python3; then
    PYTHON_BIN="$(command -v python3)"
    return
  fi
  fail "Python 3 was not found. Install Python 3.12+ and python3-venv."
}

backend_requirements_fingerprint() {
  if command_exists sha256sum; then
    sha256sum "$BACKEND_DIR/requirements.txt" | awk '{print $1}'
    return
  fi
  if command_exists shasum; then
    shasum -a 256 "$BACKEND_DIR/requirements.txt" | awk '{print $1}'
    return
  fi
  if command_exists cksum; then
    cksum "$BACKEND_DIR/requirements.txt" | awk '{print $1 ":" $2}'
    return
  fi
  fail "No checksum utility was found to validate backend dependencies."
}

backend_virtualenv_dir() {
  case "$PYTHON_BIN" in
    "$BACKEND_DIR/.venv/bin/python")
      printf '%s\n' "$BACKEND_DIR/.venv"
      ;;
    "$BACKEND_DIR/venv/bin/python")
      printf '%s\n' "$BACKEND_DIR/venv"
      ;;
    *)
      return 1
      ;;
  esac
}

backend_required_imports_work() {
  "$PYTHON_BIN" -c 'import alembic, fastapi, uvicorn; from livekit import api as livekit_api' >/dev/null 2>&1
}

ensure_backend_dependencies() {
  choose_python
  [[ -f "$BACKEND_DIR/requirements.txt" ]] || fail "apps/backend/requirements.txt was not found."

  local fingerprint
  local venv_dir=""
  local stamp_file=""
  local requirements_current=0
  local imports_current=0

  fingerprint="$(backend_requirements_fingerprint)"
  if venv_dir="$(backend_virtualenv_dir)"; then
    stamp_file="$venv_dir/.loanhub-requirements.sha256"
    if [[ -f "$stamp_file" ]] && [[ "$(cat "$stamp_file")" == "$fingerprint" ]]; then
      requirements_current=1
    fi
  else
    # A system Python has no LoanHub-owned stamp. Import validation is the source of truth.
    requirements_current=1
  fi

  if backend_required_imports_work; then
    imports_current=1
  fi

  if [[ "$requirements_current" == "1" && "$imports_current" == "1" ]]; then
    return
  fi

  if [[ "$AUTO_INSTALL" != "1" ]]; then
    fail "Backend dependencies are missing or out of date. Set LOANHUB_AUTO_INSTALL=1 or run '$PYTHON_BIN -m pip install -r apps/backend/requirements.txt'."
  fi

  if [[ -z "$venv_dir" ]]; then
    command_exists python3 || fail "python3 is required to create the backend virtual environment."
    printf 'Backend dependencies are missing or out of date; creating apps/backend/.venv ...\n'
    python3 -m venv "$BACKEND_DIR/.venv" || fail "Could not create .venv. On Ubuntu, install python3-venv first."
    PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
    venv_dir="$BACKEND_DIR/.venv"
    stamp_file="$venv_dir/.loanhub-requirements.sha256"
  else
    printf 'Backend dependencies changed or are missing; synchronizing apps/backend/requirements.txt ...\n'
  fi

  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt"
  "$PYTHON_BIN" -m pip check

  backend_required_imports_work || fail "Backend dependency installation completed, but required imports still fail."
  fingerprint="$(backend_requirements_fingerprint)"
  printf '%s\n' "$fingerprint" > "$stamp_file"
}

choose_pnpm() {
  if command_exists pnpm; then
    PNPM_CMD=(pnpm)
    return
  fi
  if command_exists corepack; then
    PNPM_CMD=(corepack pnpm)
    return
  fi
  fail "pnpm was not found. Install Node.js 22+ with pnpm, or enable Corepack."
}

frontend_dependencies_fingerprint() {
  local dependency_files=(
    "$FRONTEND_DIR/package.json"
    "$FRONTEND_DIR/pnpm-lock.yaml"
    "$FRONTEND_DIR/pnpm-workspace.yaml"
  )

  local file
  for file in "${dependency_files[@]}"; do
    [[ -f "$file" ]] || fail "${file#"$ROOT_DIR/"} was not found."
  done

  if command_exists sha256sum; then
    cat "${dependency_files[@]}" | sha256sum | awk '{print $1}'
    return
  fi
  if command_exists shasum; then
    cat "${dependency_files[@]}" | shasum -a 256 | awk '{print $1}'
    return
  fi
  if command_exists cksum; then
    cat "${dependency_files[@]}" | cksum | awk '{print $1 ":" $2}'
    return
  fi
  fail "No checksum utility was found to validate frontend dependencies."
}

ensure_frontend_dependencies() {
  command_exists node || fail "Node.js was not found. LoanHub frontend requires Node.js."
  choose_pnpm

  # In check-only mode we never mutate node_modules. An existing installation is
  # enough to launch through `pnpm exec`; pnpm itself resolves the local Next.js
  # binary. This also lets lightweight/test worktrees run without copying the
  # lockfile solely for a no-install launch.
  if [[ "$AUTO_INSTALL" != "1" ]]; then
    [[ -d "$FRONTEND_DIR/node_modules" ]] || fail "Frontend dependencies are missing. Set LOANHUB_AUTO_INSTALL=1 or run 'cd apps/frontend && CI=true pnpm install --frozen-lockfile --prefer-offline'."
    return
  fi

  local fingerprint
  local stamp_file="$FRONTEND_DIR/node_modules/.loanhub-dependencies.sha256"
  local next_bin="$FRONTEND_DIR/node_modules/.bin/next"

  fingerprint="$(frontend_dependencies_fingerprint)"

  if [[ -x "$next_bin" && -f "$stamp_file" ]] && [[ "$(cat "$stamp_file")" == "$fingerprint" ]]; then
    return
  fi

  if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
    printf 'Frontend dependencies changed or were installed by a different pnpm version; synchronizing node_modules ...\n'
  else
    printf 'Frontend dependencies are missing; running pnpm install ...\n'
  fi

  # start.sh launches services in the background, so pnpm has no interactive TTY.
  # CI=true explicitly permits pnpm to rebuild an incompatible node_modules tree
  # instead of aborting with ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY.
  (
    cd "$FRONTEND_DIR"
    CI=true "${PNPM_CMD[@]}" install --frozen-lockfile --prefer-offline
  ) || fail "Frontend dependency synchronization failed. Check the pnpm output above."

  [[ -x "$next_bin" ]] || fail "Frontend dependency installation completed, but Next.js was not installed correctly."
  fingerprint="$(frontend_dependencies_fingerprint)"
  printf '%s\n' "$fingerprint" > "$stamp_file"
}

check_environment() {
  [[ -d "$BACKEND_DIR" ]] || fail "apps/backend was not found. Run this command from the LoanHub repository."
  [[ -d "$FRONTEND_DIR" ]] || fail "apps/frontend was not found. Run this command from the LoanHub repository."
  [[ -f "$BACKEND_DIR/main.py" ]] || fail "apps/backend/main.py was not found."
  [[ -f "$FRONTEND_DIR/package.json" ]] || fail "apps/frontend/package.json was not found."

  ensure_backend_dependencies
  ensure_frontend_dependencies

  if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    printf 'Warning: apps/backend/.env was not found. FastAPI will use exported environment variables and defaults.\n' >&2
  fi

  if [[ ! -f "$FRONTEND_DIR/.env.local" && -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
    export NEXT_PUBLIC_API_URL="http://localhost:${BACKEND_PORT}/api/v1"
    printf 'Frontend API URL: %s (temporary default for this run)\n' "$NEXT_PUBLIC_API_URL"
  fi
}

run_database_migrations() {
  if [[ "$RUN_MIGRATIONS" != "1" ]]; then
    printf 'Skipping LoanHub database migrations because LOANHUB_RUN_MIGRATIONS=%s.\n' "$RUN_MIGRATIONS"
    return
  fi

  printf '\nApplying LoanHub database migrations...\n'
  (
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" -m alembic upgrade head
  ) || fail "Database migration failed. LoanHub was not started. Check the database connection and Alembic migration state."
  printf 'LoanHub database migrations are up to date.\n'
}

stop_process_tree() {
  local pid="${1:-}"
  [[ -n "$pid" ]] || return 0
  if kill -0 "$pid" 2>/dev/null; then
    if command_exists pkill; then
      pkill -TERM -P "$pid" 2>/dev/null || true
    fi
    kill -TERM "$pid" 2>/dev/null || true
  fi
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$BACKEND_PID" || -n "$FRONTEND_PID" ]]; then
    printf '\nStopping LoanHub services...\n'
  fi
  stop_process_tree "$FRONTEND_PID"
  stop_process_tree "$BACKEND_PID"
  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  exit "$status"
}

start_local() {
  check_environment

  port_is_busy "$BACKEND_PORT" && fail "Backend port ${BACKEND_PORT} is already in use. Set BACKEND_PORT to another port or stop the existing process."
  port_is_busy "$FRONTEND_PORT" && fail "Frontend port ${FRONTEND_PORT} is already in use. Set FRONTEND_PORT to another port or stop the existing process."

  run_database_migrations

  trap cleanup EXIT INT TERM

  printf '\nStarting LoanHub backend...\n'
  (
    cd "$BACKEND_DIR"
    exec "$PYTHON_BIN" -m uvicorn main:app \
      --host "$BACKEND_HOST" \
      --port "$BACKEND_PORT" \
      --reload
  ) &
  BACKEND_PID=$!

  printf 'Starting LoanHub frontend...\n'
  (
    cd "$FRONTEND_DIR"
    exec "${PNPM_CMD[@]}" exec next dev \
      --hostname "$FRONTEND_HOST" \
      --port "$FRONTEND_PORT"
  ) &
  FRONTEND_PID=$!

  printf '\nLoanHub is starting with one launcher:\n'
  printf '  Frontend: http://localhost:%s\n' "$FRONTEND_PORT"
  printf '  Backend:  http://localhost:%s\n' "$BACKEND_PORT"
  printf '  API docs: http://localhost:%s/docs\n' "$BACKEND_PORT"
  printf 'Press Ctrl+C once to stop both services.\n\n'

  set +e
  wait -n "$BACKEND_PID" "$FRONTEND_PID"
  local status=$?
  set -e

  if kill -0 "$BACKEND_PID" 2>/dev/null && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    printf 'Frontend stopped; shutting down backend.\n' >&2
  elif kill -0 "$FRONTEND_PID" 2>/dev/null && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    printf 'Backend stopped; shutting down frontend.\n' >&2
  fi

  return "$status"
}

case "${1:-}" in
  "")
    start_local
    ;;
  --check)
    check_environment
    printf 'LoanHub local startup prerequisites look ready.\n'
    ;;
  --docker)
    [[ -f "$ROOT_DIR/scripts/docker-up.sh" ]] || fail "scripts/docker-up.sh is missing."
    exec sh "$ROOT_DIR/scripts/docker-up.sh"
    ;;
  --help|-h)
    usage
    ;;
  *)
    usage >&2
    fail "Unknown option: $1"
    ;;
esac
