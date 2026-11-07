#!/usr/bin/env bash
# Future verification entrypoint for the consolidated Wacom code candidate.
# DO NOT invoke during coding-only preparation. No deploy, migration or merge.
set -Eeuo pipefail

if [[ "${1:-}" != "--execute-offline-tests" || "$#" -ne 1 ]]; then
  cat <<'HELP'
This script runs Wacom's offline development tests and builds the Go connector.
It does not deploy, migrate a database or authorize document signing.

Later, after review, explicitly run:
  bash scripts/wacom_verify_code_only.sh --execute-offline-tests

For real ClamAV, PostgreSQL, HTTPS staging and physical STU-540 tests,
follow the independent staging acceptance plan. This script does not run them.
HELP
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ROOT/services/wacom-connector/go.mod" || ! -f "$ROOT/apps/backend/requirements.txt" ]]; then
  echo "LoanHub repository layout not found" >&2
  exit 2
fi
if [[ -n "${CI:-}" && "${CI:-}" != "true" ]]; then
  echo "Refusing ambiguous CI configuration" >&2
  exit 2
fi

echo "[Wacom] Offline Go unit and synthetic HTTPS integration tests"
(
  cd "$ROOT/services/wacom-connector"
  go test ./...
  go build ./...
)

echo "[Wacom] Offline Python API, evidence review and validation tests"
(
  cd "$ROOT/apps/backend"
  python -m pytest -q \
    tests/test_local_signatures_api.py \
    tests/test_local_signature_evidence_review.py \
    tests/test_wacom_api_contract_conformance.py \
    tests/test_wacom_png_validation.py \
    tests/test_wacom_real_api_smoke.py \
    tests/test_wacom_signature_use_authorization_status.py
)

echo "[Wacom] Code-only verification passed."
echo "[Wacom] Not a production approval or an actual STU-540/staging validation."
