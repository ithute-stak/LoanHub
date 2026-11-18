# Phase 78 — Concurrent normalized-index rollout rehearsal

Phase 77 provides read-only collision and blank-identity counts. Phase 78
implements **isolated PostgreSQL migration rehearsals**, NOT a production
migration, deployment script or approval mechanism.

## What is exercised

In a fresh `loanhub_identity_rollout_sandbox` CI database, each test creates
an independently generated schema with **synthetic** `people` and `users`
tables. The suite calls real PostgreSQL `CREATE UNIQUE INDEX CONCURRENTLY`
for national IDs, passports, phones and emails, matching the reviewed index
design, using an autocommit connection.

For each identity column, the tests validate that:
- An index with no conflicting normalized identity is unique, valid, ready
  and blocks a case/whitespace-equivalent duplicate, while preserving the
  previous row.
- A concurrent unique-index build on existing normalized duplicates fails.
  Any leftover invalid index is dropped with `DROP INDEX CONCURRENTLY`.
  Both original synthetic records remain intact.

All isolated schemas are dropped after the tests. No customer identities or
loan, payment, repayment, legacy-loan or settlement records are queried or
changed. Production indexes are **not** installed. These tests are required
in CI rather than silently skipped.

## Important operational limitations

1. Production rollout requires review of *real* duplicate identity groups,
   existing writable applications, index collation and partial predicates.
   The tests use only synthetic data.
2. A PostgreSQL concurrent-index operation **cannot** be executed in a
   regular Alembic migration transaction; use an explicitly reviewed DBA
   maintenance runbook with autocommit and invalid-index cleanup.
3. Live systems can have concurrent writes while an index builds. An audit
   and coordinated control of all identity-writing services are required.
4. A cancelled operation can leave an invalid index and needs independent
   inspection before a retry. Never delete or overwrite old client records
   merely to make a uniqueness migration pass.
5. No new public client registration route or Batlokoa write activation is
   introduced. Explicit security, domain and DBA approval is still required.

Phase 78 does not certify a migration against production-like data. It
certifies only the database-level behavior of the candidate SQL in an
independent sandbox.
