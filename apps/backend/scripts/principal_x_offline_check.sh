#!/usr/bin/env bash
# Principal x% offline fast-track checks.
# No network, database, migrations, Git pushes, or production writes.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BACKEND="$ROOT/apps/backend"
cd "$BACKEND"

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sqlalchemy' >/dev/null 2>&1; then
  echo "Missing local backend dependencies. Use an existing backend virtualenv; this script never installs packages." >&2
  exit 2
fi

echo "[1/4] Compile Principal x modules and tests"
"$PYTHON" -m compileall -q payment_engine/principal_x_*.py \
  services/principal_x_*.py \
  services/company_payment_model_settings_service.py \
  services/loan_payment_model_assignment_service.py \
  services/loan_payment_model_assignment_writer.py \
  scripts/audit_principal_x_alembic_graph.py \
  tests/test_principal_x_*.py

echo "[2/4] Verify Alembic revision graph (read-only)"
"$PYTHON" -m scripts.audit_principal_x_alembic_graph

echo "[3/4] Run focused Principal x unit tests"
"$PYTHON" -m pytest -q tests/test_principal_x_*.py

echo "[4/4] Verify no calculator changes in this branch"
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  if git diff --name-only origin/main...HEAD -- \
      apps/backend/services/interest_calculation_service.py \
      apps/frontend | grep -E '(^apps/backend/services/interest_calculation_service.py$|calculator|Calculator)' ; then
    echo "BLOCKED: calculator-related files differ from origin/main" >&2
    exit 1
  fi
else
  echo "NOTE: origin/main is unavailable locally; calculator diff check skipped."
fi

echo "Offline checks passed. This is NOT a substitute for full CI, database migration rehearsal, or review."
