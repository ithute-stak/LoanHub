#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
TEMP_ENV_CREATED=0

cleanup() {
  if [[ "$TEMP_ENV_CREATED" -eq 1 ]]; then
    rm -f "$ROOT_DIR/.env"
  fi
}
trap cleanup EXIT

bash "$ROOT_DIR/scripts/test_production_deploy_guard.sh"

cd "$ROOT_DIR/apps/backend"
"$PYTHON_BIN" -m compileall -q .
"$PYTHON_BIN" -m pytest -q \
  tests/test_external_debt_tracking.py \
  tests/test_financial_and_tenant_invariants.py \
  tests/test_global_borrower_lookup_frontend.py \
  tests/test_global_borrower_history_print_frontend.py \
  tests/test_fullscreen_borrower_lookup_toolbar_frontend.py \
  tests/test_global_sticky_filter_rollout_frontend.py \
  tests/test_hrms_native_module.py \
  tests/test_hrms_hybrid_navigation_frontend.py \
  tests/test_cdas_auth_session_negotiation.py \
  tests/test_cdas_company_configuration.py \
  tests/test_cdas_employee_verification.py \
  tests/test_cdas_read_operations.py \
  tests/test_cdas_write_operations.py \
  tests/test_cdas_phase2_frontend.py \
  tests/test_cdas_management_frontend.py
"$PYTHON_BIN" -m alembic heads

if [[ "${LOANHUB_VALIDATE_LIVE_MIGRATIONS:-false}" == "true" ]]; then
  echo "[LoanHub] Validating full Alembic upgrade against disposable PostgreSQL"
  "$PYTHON_BIN" -m alembic upgrade head
  current_revision="$("$PYTHON_BIN" -m alembic current | awk 'NF {print $1; exit}')"
  head_revision="$("$PYTHON_BIN" -m alembic heads | awk 'NF {print $1; exit}')"
  if [[ "$current_revision" != "$head_revision" ]]; then
    echo "[LoanHub] Migration verification failed: current=$current_revision head=$head_revision" >&2
    exit 1
  fi
  echo "[LoanHub] Alembic reached head: $head_revision"
fi

cd "$ROOT_DIR/apps/frontend"
pnpm typecheck
pnpm lint
pnpm build

cd "$ROOT_DIR"
if [[ ! -f .env ]]; then
  cp .env.example .env
  TEMP_ENV_CREATED=1
fi
LOANHUB_ENV_FILE=.env docker compose config >/dev/null
printf 'LoanHub project validation passed.\n'
