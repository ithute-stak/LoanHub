# Phase 64 — Transaction-scoped identity locking (preparatory only)

The helper `check_with_transaction_identity_locks` acquires deterministic
PostgreSQL `pg_advisory_xact_lock` locks for **normalized, globally scoped**
national ID, passport, phone and email values, in sorted order. It then calls
the Phase 63 read-only candidate guard. All operations run inside a
caller-owned transaction; the helper never commits, creates an identity,
links a borrower, or changes any loan.

## Why it remains disabled for registration

Advisory locks only protect cooperating code paths. The existing LoanHub
assisted registration, borrower onboarding, imports, and other writers do
not all use this lock protocol. Consequently locks do **not** guarantee
uniqueness, and neither a clear match nor a successful lock acquisition
permits client creation. The helper's result remains `candidate=false`.
Do not use this as a production write gate.

## Required for safe registration activation

1. Audit and remediate pre-existing normalized identity collisions without
   automatically merging or overwriting historical accounts.
2. Add database-enforced normalized uniqueness with a carefully reviewed
   migration (not included here), coordinating every identity writer.
3. Build a separate new-client-only transactional endpoint with
   rollback-safe idempotency, explicit branch assignment, audit trail and
   conservative rejection of any existing borrower/legacy match.
4. Validate two concurrent employees submitting the same identity using an
   isolated PostgreSQL staging environment. Verify exactly one authorized
   creation, no orphan identities and no historical balance changes.
5. Only then enable Batlokoa's staff registration submit action.

The helper must never be called with user-controlled tenant or role context.
It is not a substitute for LoanHub native RBAC, branch scope or DB constraints.

No production database migration, deployment, personal data access or
financial transaction is introduced in this phase.
