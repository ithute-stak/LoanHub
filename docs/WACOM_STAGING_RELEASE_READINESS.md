# Wacom Phase 17 — Isolated staging release readiness

Release-readiness checks only. This is NOT a deployment, merger, or permission to sign contracts.

## Stacked development PRs

PRs #586–#599 and #601 collectively provide LoanHub local PC authentication, Wacom SDK captures, encrypted pending-review evidence, read-only contract checks, simulated TLS integration, disposable PostgreSQL tests and real ClamAV tests. GitHub Actions #2472 passed. All remain draft and require review before merging.

## Static staging gate

Execute on an isolated test backend with its actual approved test-only configuration:

```bash
cd apps/backend
python -m pytest -q tests/test_wacom_staging_readiness.py
python scripts/wacom_staging_readiness.py --check
```

The script checks explicitly isolated HTTPS API host, test/staging backend environment, dedicated PostgreSQL test/staging database, separate test storage or bucket, encryption key, enabled scanning and fail-closed scanner settings. It performs no network calls or deployment.

Passing the static gate does not prove real separation from production or confirm scanner, DB or storage availability. Operators must independently inspect isolation, certificates, credentials, encryption key separation and backups before integration tests.

## Controlled acceptance sequence

1. Independently review stacked PRs and create a separate staging deployment of the **existing** LoanHub backend.
2. Use dedicated credentials, database, storage, encryption key, scanner and synthetic staff/borrower records.
3. Verify runtime configuration, complete database migrations and safe backup/recovery.
4. Run unauthenticated smoke checks, then synthetic operator login and borrower lookup.
5. Test synthetic PNG upload, actual encrypted readback, scanner rejection and outage, independent review and audit.
6. Deny cross-tenant read, preview, review and status requests.
7. Verify cleanup of synthetic captures and the corresponding audit chain.
8. On the physical STU-540 PC test browser-triggered capture and preview with meaningless scribbles, not real signatures.

No Wacom SDK is installed on the VPS. Captures and reviewed evidence may not sign or be reused for a contract without fresh, borrower-verified consent tied to the exact document hash/version and an atomic finalization operation.