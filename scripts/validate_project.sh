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
  tests/test_hrms_hybrid_navigation_frontend.py
"$PYTHON_BIN" -m alembic heads
"$PYTHON_BIN" -m alembic upgrade head --sql >/tmp/loanhub-upgrade.sql
"$PYTHON_BIN" -m alembic downgrade head:base --sql >/tmp/loanhub-downgrade.sql

cd "$ROOT_DIR/apps/frontend"
pnpm typecheck
pnpm lint
pnpm build

cd "$ROOT_DIR"
if [[ ! -f .env ]]; then
  cp .env.example .env
  TEMP_ENV_CREATED=1
fi
docker compose config >/dev/null
printf 'LoanHub project validation passed.\n'
