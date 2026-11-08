#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/tools/verify_bundle.py"
PYTHONPATH="$ROOT/payload/apps/backend${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q \
  "$ROOT/payload/apps/backend/tests/test_wacom_document_policy.py"
echo 'Standalone domain tests passed. Full app + Go tests require applying to a LoanHub checkout.'
