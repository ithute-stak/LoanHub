# Wacom Phase 14 — PostgreSQL tenant-scoped review integration

This phase adds **opt-in actual PostgreSQL SQL integration tests** for the
existing Wacom review endpoint. These do **not** use real borrowers,
company records, handwriting, or any deployed LoanHub database.

## CI and test prerequisites

The test uses a **dedicated local/CI PostgreSQL database** with:
- Hostname exactly `localhost`, `127.0.0.1` or `::1`
- Database name ending `_test`
- `WACOM_PG_TEST_URL` pointing to that database
- Permission to CREATE and DROP a uniquely named disposable schema

If the environment variable is absent, pytest **skips** these tests.
An ordinary CI-green result therefore does **not** prove that the actual
PostgreSQL tests executed: look for test counts and skipped tests.

To test using a locally isolated temporary PostgreSQL instance:

```bash
docker run --rm -d --name wacom-pg-test \
  -e POSTGRES_USER=wacom_test \
  -e POSTGRES_PASSWORD=wacom_test_only \
  -e POSTGRES_DB=wacom_isolation_test \
  -p 127.0.0.1:55439:5432 postgres:16-alpine

# After PostgreSQL is ready:
cd apps/backend
export WACOM_PG_TEST_URL='postgresql+psycopg://wacom_test:wacom_test_only@127.0.0.1:55439/wacom_isolation_test'
python -m pytest -q tests/test_wacom_postgresql_review_isolation.py -rs
unset WACOM_PG_TEST_URL

docker stop wacom-pg-test
```

The URL and password above are **disposable local test values** and must
never be reused in any staging or production system.

## What the tests verify on actual PostgreSQL

1. Two different company UUIDs are inserted as fictional managed files.
2. The reviewer's company queue returns only its own company's evidence.
3. Reviewing another company's known file ID returns HTTP 404.
4. Uploading operator cannot independently approve that same evidence.
5. A permitted reviewer changes the correct file to verified.
6. A matching audit log is written by the same database transaction.
7. Repeating the same decision cannot approve already-reviewed evidence.
8. A cross-tenant preview is denied **before** file bytes are read.
9. Authorized preview preserves no-store controls.

## Scope limits that must not be misrepresented

These tests use the actual LoanHub SQLAlchemy ORM and PostgreSQL query
execution, but create lightweight disposable copies of `managed_files`
and `audit_logs` with no production foreign-key graph.

**These tests do not establish PostgreSQL row-level security (RLS).**
LoanHub's database tenant context code explicitly says that it does not
enable RLS policies. RLS configuration and permission boundary audits
remain distinct requirements, along with real-file object storage and
ClamAV verification.

No Wacom service runs on the VPS; no production deployment is included.
