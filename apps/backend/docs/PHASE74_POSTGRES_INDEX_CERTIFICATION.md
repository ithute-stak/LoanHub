# Phase 74 — Normalized identity index certification (isolated Postgres)

Phase 73 is merged into LoanHub main, but its internal registration service
requires four valid/ready normalized unique indexes. **No production migration
to create these indexes is included in this phase.**

## Run the opt-in PostgreSQL contract suite

Use only a dedicated disposable PostgreSQL database. Its name must end in
`_test`, `_ci`, or `_sandbox`. Tests additionally require an explicit
acknowledgement:

```bash
cd apps/backend
export LOANHUB_REGISTRATION_STAGING_POSTGRES_URL='postgresql+psycopg://test_user:***@test_host:5432/loanhub_registration_sandbox'
export LOANHUB_REGISTRATION_STAGING_ACK='isolated_disposable_database'
pytest -q tests/test_new_client_normalized_indexes_postgres.py
```

The suite creates a fresh randomly named schema containing **synthetic**
`people`/`users` probe tables, creates the four candidate indexes inside
it, validates the same catalog checks required by the Phase 73 writer, and
drops that schema in `finally`. The tests never query or modify real
LoanHub identities, customer accounts, bank details, loans or repayments.

The tests cover:

- The internal registration writer's index-verification gate failing when
  indexes are absent, then accepting valid PostgreSQL definitions.
- Uniqueness across trimmed/case-folded national IDs, passports, phones,
  and emails, while retaining the prior row after a failed duplicate insert.
- A failed unique-index build against synthetic existing duplicates leaving
  historical rows unchanged.

## Real migration approval gates

1. Obtain a backup and a privacy-restricted, representative reporting clone.
2. Run the Phase 65 collision audit and verify the behavior of other global
   identity writers, including legacy import and borrower self-onboarding.
3. Review exact index names, default collation, predicates and ORM
   normalization. The SQL shown by Phase 66 is **design-only**.
4. Remediate collisions individually under approved operational procedures;
   never merge/delete legacy loans or change settled flags automatically.
5. Test an actual `CREATE UNIQUE INDEX CONCURRENTLY` rollout in isolated
   staging, including a failed rollout, invalid-index cleanup and operator
   rollback. Plan for the fact that concurrent index creation cannot run
   inside a normal Alembic transaction.
6. Perform end-to-end tests against LoanHub's real new-only service models,
   idempotency records, tenant/branch authorization, fees, and transaction
   rollback with realistic but synthetic fixtures.
7. Obtain explicit operations/security approval before introducing a
   production migration and a separately gated API route.

**No production uniqueness indexes or client records are changed here.
Successful CI unit tests do not mean the opt-in PostgreSQL suite ran.**
