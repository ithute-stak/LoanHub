#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

cat <<'EOF'
LoanHub safe migration
----------------------
Stop Uvicorn, maintenance workers, Celery/RQ workers, and every second
Alembic process before continuing. Back up PostgreSQL before production
schema changes.
EOF

if [[ ! -f .env ]]; then
    echo "Missing .env. Run ./scripts/generate_secrets.sh first." >&2
    exit 1
fi

HEAD_COUNT="$(alembic heads | grep -c '(head)' || true)"

if [[ "$HEAD_COUNT" -ne 1 ]]; then
    echo "Expected exactly one Alembic head; found $HEAD_COUNT." >&2
    alembic heads >&2
    exit 1
fi

python -m compileall -q     api core database routers services utils main.py

python scripts/validate_release.py

echo
echo "Current database revision:"
alembic current

echo
echo "Applying migrations:"
alembic upgrade head

echo
echo "Verifying database/model alignment:"
alembic current
alembic check

echo
echo "LoanHub migration completed successfully."
