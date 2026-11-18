# Phase 67 — Isolated PostgreSQL client-identity concurrency tests

This phase adds opt-in integration tests for the **building blocks** needed
by Batlokoa staff client registration. These are not tests against production
LoanHub borrowers.

## Test setup

Run under `apps/backend` using an approved, **disposable PostgreSQL
database with an isolated test-only database user**, not a production
connection:

```bash
LOANHUB_CLIENT_IDENTITY_TEST_POSTGRES_URL='postgresql+psycopg://...' \
  pytest -q tests/test_new_client_identity_concurrency_postgres.py
```

When the environment variable is absent, both tests skip. Each test creates
a unique disposable `client_identity_probe_<random>` table and removes it
in `finally`. No customer/borrower/loan/repayment/payment tables are read or
written. Never set the DSN to a production or shared LoanHub database.

## Covered contracts

1. Two concurrent workers representing separate branches synchronize their
   requests and use normalized, **globally scoped** PostgreSQL transaction
   advisory locks. Both return the same synthetic identity row, but only one
   insertion occurs.
2. A normalized unique index rejects a duplicate national ID even with
   different case and surrounding spaces; a savepoint rollback preserves the
   original synthetic row and leaves the outer transaction usable.
3. The Phase 64 lock key categorization is corrected so the mandatory ID
   check uses the correct segment of the canonical namespaced lock key.

## Remaining gaps before enabling registration

These tests validate a synthetic locking and index **contract**, not the
full LoanHub registration service. There is no new-only client creation
endpoint, production index migration, global writer participation,
validated idempotency, forensic legacy identity resolution or borrower state
invariant integration test. The real production borrower, loan balance and
settlement state have **not** been exercised here.

Keep Batlokoa's client registration disabled until collision remediation,
reviewed normalized DB constraints, end-to-end registration service tests,
rollback verification and explicit staged deployment acceptance are complete.
