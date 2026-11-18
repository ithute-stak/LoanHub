# Phase 66 — Normalized identity index readiness (non-mutating)

LoanHub contains existing exact-value uniqueness for identity columns; that
is not sufficient for the case-insensitive, whitespace-trimmed matching used
by the client registration services.

This internal, read-only audit reports:
- Aggregate count of normalized collision groups in persons' national IDs,
  passports, users' phones and emails.
- Whether specifically named unique normalized indexes appear present, valid
  and unique in PostgreSQL.
- Static, *proposed* `CREATE UNIQUE INDEX CONCURRENTLY` definitions for DBA
  design review only. The module **never executes DDL** or changes clients.

The audit intentionally leaves `safe_to_apply_migration=false` and
`registration_enabled=false` on **every outcome**. The
`migration_review_candidate` field means only that four aggregate normalized
identity scans reported no repeated groups. It is not evidence that indexes
can be deployed without further review.

## Staging approval gates

1. Inventory existing bad/blank/legacy identities and all identity-writing
   code paths; preserve existing borrower financial state.
2. Review indexes' complete definition, collation, predicate and schema,
   index creation lock behavior and all application normalization semantics.
3. On a separate PostgreSQL staging clone, test concurrent insert/update,
   unique constraint enforcement, migration abort, rollback and old-account
   reconciliation without deleting or merging any historical account.
4. Audit idempotency and cross-branch requests for a dedicated *new-only*
   registration API; block any fallback into existing-borrower reuse.
5. Require explicit DBA, lending domain and security approval before a
   production migration, then separate controlled feature activation.

The module exposes no public endpoint, performs no migrations and makes no
claim that real production data has been inspected.
