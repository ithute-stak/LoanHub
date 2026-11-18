# Phase 75 — Real LoanHub registration transactions in isolated PostgreSQL

Phase 74 passed **real** PostgreSQL index certification and was merged. Phase 75
tests the complete **internal** `create_new_client_atomically` service against
LoanHub's actual migrated database columns, constraints and ORM models.

## Execution

The LoanHub CI job creates a *new, empty, disposable* PostgreSQL database named
`loanhub_registration_e2e_sandbox` in the CI PostgreSQL service. It applies
all Alembic migrations to that database, sets the isolated-test acknowledgement
and executes:

```bash
python -m pytest -q -ra --maxfail=1 \
  tests/test_atomic_new_client_real_models_postgres.py
```

Each test creates a new random schema and clones the production-schema
`users`, `people`, `borrowers`, `company_borrower_accounts`,
`new_client_registration_attempts`, `legacy_loan_captures`,
`audit_logs` and fee-configuration table structures using PostgreSQL
`LIKE ... INCLUDING ALL`. **Only structures are copied; no borrower rows,
customer information, loan records or balances are imported.** Foreign keys
are not cloned, so referential enforcement against real company and staff
tables is outside this suite's scope. A test-only copy of the four required
normalized unique indexes is created inside each disposable schema; no
production identity indexes are installed.

All calls exercise the real LoanHub transaction coordinator, locking guard,
ORM staging and idempotency completion. They verify:

- One new person, borrower, company client, audit event and idempotency
  completion are saved together, correctly bound to employee and branch.
- Exact replay returns the original account with no duplicate records.
- A different request key using a normalized duplicate national ID is
  rejected without changing existing records.
- A historical capture from another company blocks unsafe registration and
  remains unchanged, including paid, borrowed and total amounts.
- An injected failure after staging rolls back **all** writes.
- Two simultaneous requests for the same identity and idempotency key
  create only one account.

## Remaining before rollout

1. Add complete referential-integrity tests with actual company/staff rows,
   account fee configuration and realistic legacy loan/balance models.
2. Build a reviewed production normalized-index migration only after a
   privacy-restricted collision audit on real data; coordinate other writers.
3. Protect session/credential delivery, birth date validation, staff session
   permissions, security audit and full form fields (banking, employment,
   debts). Phase 73 rejects unsupported fields to prevent data loss.
4. Explicit approval for any application API route and a separate staged
   Batlokoa feature activation.

**No production database is touched and registration remains disabled.**
CI success must be checked at the exact commit and must show this specific
PostgreSQL step succeeded; ordinary Python unit tests alone are insufficient.
