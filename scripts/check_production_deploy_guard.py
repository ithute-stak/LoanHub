#!/usr/bin/env python3
"""Static checks for LoanHub's production deployment safety contract."""

from pathlib import Path


script = Path(__file__).with_name("deploy-production-manual.sh").read_text(encoding="utf-8")

required_fragments = {
    "forward-only commit ancestry guard": "REFUSING non-forward release",
    "live Alembic revision compatibility guard": "LOANHUB_REQUIRED_ALEMBIC_REVISION",
    "fail-closed migration execution": "run --rm --no-deps migrate",
    "safe latest workflow selection": "actions/workflows/release-images.yml/runs?branch=main&status=success",
    "application start without re-running migration dependency": "up -d --no-build --pull never --no-deps backend",
}

missing = [name for name, fragment in required_fragments.items() if fragment not in script]
if missing:
    raise SystemExit("Production deployment safety checks missing: " + ", ".join(missing))

if 'up --no-build --pull never migrate' in script:
    raise SystemExit("Migration execution must propagate the migrate container exit code.")

print("LoanHub production deployment safety contract is present.")
