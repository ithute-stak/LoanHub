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
    "candidate backend import smoke": "Running candidate backend import smoke before database migration or application cutover",
    "rollback image preflight": "ensure_rollback_image",
    "rollback release preservation": "Securing current release $current_release locally for automatic rollback",
    "automatic rollback arming": "rollback_armed=1",
    "failed release marker": "releases/last-failed.sha",
    "in-progress release marker": "releases/deploying.sha",
    "rollback image selection": 'export LOANHUB_IMAGE_TAG="$rollback_release"',
    "rollback backend recreation": 'up -d --no-build --pull never --no-deps backend || rollback_ok=0',
    "rollback frontend recreation": 'up -d --no-build --pull never --no-deps maintenance frontend || rollback_ok=0',
    "rollback public verification": "verify_public_endpoints || rollback_ok=0",
    "interrupted deployment rollback": "trap 'handle_deployment_signal HUP 129' HUP",
    "atomic production release marker": 'write_release_marker releases/current.sha "$RELEASE_SHA"',
}

missing = [name for name, fragment in required_fragments.items() if fragment not in script]
if missing:
    raise SystemExit("Production deployment safety checks missing: " + ", ".join(missing))

if 'up --no-build --pull never migrate' in script:
    raise SystemExit("Migration execution must propagate the migrate container exit code.")


def require_before(first: str, second: str, description: str) -> None:
    first_index = script.find(first)
    second_index = script.find(second)
    if first_index < 0 or second_index < 0 or first_index >= second_index:
        raise SystemExit(f"Production deployment ordering violated: {description}")


require_before(
    'docker pull "$BACKEND_IMAGE:$RELEASE_SHA"',
    'deployment_phase="backend cutover"',
    "candidate backend image must be pulled before backend cutover",
)
require_before(
    'docker pull "$FRONTEND_IMAGE:$RELEASE_SHA"',
    'deployment_phase="backend cutover"',
    "candidate frontend image must be pulled before backend cutover",
)
require_before(
    'Securing current release $current_release locally for automatic rollback',
    'Applying Alembic migrations (fail-closed)',
    "rollback images must be secured before database migration",
)
require_before(
    'Running candidate backend import smoke before database migration or application cutover',
    'Applying Alembic migrations (fail-closed)',
    "candidate backend import smoke must run before database migration",
)
require_before(
    'rollback_armed=1',
    'deployment_phase="backend cutover"',
    "automatic rollback must be armed before replacing the backend",
)
require_before(
    'deployment_phase="public endpoint verification"',
    'write_release_marker releases/current.sha "$RELEASE_SHA"',
    "production release marker must only change after public verification",
)

print("LoanHub production deployment safety contract is present.")
