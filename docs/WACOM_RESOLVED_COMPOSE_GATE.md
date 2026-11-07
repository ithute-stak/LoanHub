# Phase 19 — Resolved staging Compose isolation verification

**CI-only structural validation, not a deployment.** This checks the *effective resolved Docker Compose model*, rather than relying solely on reading the overlay YAML.

## What the CI step checks

- Unique `loanhub-wacom-stage` Compose project and project-scoped PostgreSQL, Redis and file volumes.
- Dedicated `loanhub_wacom_staging` / `loanhub_wacom_test` database.
- Backend staging environment, HTTPS routing still requiring separate approval, encryption enabled, and fail-closed ClamAV scanning.
- API port 8000 mapped only to 127.0.0.1 on a staging-only host port.
- ClamAV has no host-published port and no public/edge network is attached.
- Backend and migration secrets are mounted from a staging-only read-only location.
- Payments remain disabled by the relevant existing staging setting.

The GitHub Actions job constructs an ephemeral synthetic env file, calls `docker compose config --format json`, pipes its output to `wacom_resolved_compose_gate.py`, and executes adversarial unit tests. It does not print resolved config, which can contain credentials.

## Important boundaries

A passing result is **not evidence** of runtime database, network or credential separation. These checks do not start or deploy services. Existing LoanHub integrations other than the explicitly disabled services require separate review, and this blueprint does not authorize signing or live customers.

Review and merge the stacked draft Wacom changes only through the approved release process. Run actual isolated staging smoke tests after independent infrastructure/security approval.