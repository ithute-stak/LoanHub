# Phase 70 — Atomic *new-only* client row staging (not activated)

Phase 70 introduces an **internal** staging function,
`stage_new_only_client_rows`, which uses a caller-owned PostgreSQL
transaction. It can stage a *new* LoanHub User, Person, Borrower,
CompanyBorrowerAccount, and AuditLog together with `flush` operations and
**no commit**. This function never loads/updates an existing borrower,
touches a loan or repayment, or uses legacy assisted registration.

The staging primitive is disabled by default and accepts an internal-call
argument intended only for isolated tests and future reviewed orchestration.
**That argument is not a security boundary.** Do not wire this function to
any API, command, worker, or administrative tool before completion of all
activation prerequisites. In particular, it does not itself verify KYC,
existing identity, unique indexes, idempotency reservation, complete staff
authorization or fees.

This is not yet a working new-client creation transaction. The active
`execute_new_only_registration` entry point still unconditionally rejects
writes. No production database transaction has been run.

## Required before safe activation

1. Correctly apply and verify the Phase 69 idempotency migration in a
   disposable PostgreSQL staging environment, with one Alembic head.
2. Add normalized unique database constraints across all global identity
   writers, after inspecting/remediating collisions.
3. Integrate tenant/branch permission checks, idempotency reservation,
   global identity locks, no-existing-user checks, safe account fee
   configuration, new-only inserts, idempotency completion and audit in
   **one** transaction; commit only once after all checks.
4. Reject any existing borrower identity rather than overwriting global
   borrower employment, bank or debt information.
5. Verify rollback on failed inserts and concurrent requests, opening-fee
   handling, generated account references, temporary password delivery,
   and legacy loan balance/settlement invariants.
6. Use a dedicated new-only endpoint gated by a reviewed configuration
   with explicit production approval; only then connect Batlokoa UI.

**No real client creation, migration deployment, loan modification or
registration activation is included in this phase.**
