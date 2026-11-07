# Phase 37 — Tenant integrity and reservation evidence (inactive)

This phase adds **tests and a pure evidence contract**, NOT a payment engine,
a production migration or a finance API activation.

## Delivered
- `services/batlokoa_reservation_evidence.py`: canonical SHA-256 event
  evidence digest and hash-chain ordering/tenant-link verification.
- `tests/test_batlokoa_reservation_evidence.py`: alteration, wrong digest,
  sequence gap and cross-reservation failure tests.
- `tests/fixtures/batlokoa_phase37_isolated_rls.sql`: **test fixture only**
  with composite tenant/loan and tenant/borrower FKs, RLS and no update/delete
  privileges for a restricted actor.
- `tests/test_batlokoa_reservation_rls_postgres.py`: disposable schema and
  role tests for cross-tenant reads/writes, missing transaction scope,
  composite FK mismatch and denied record mutation.
- Dedicated GitHub Actions PostgreSQL 16 certification workflow.

## Explicit limitations
- The SQL fixture operates on synthetic test tables, not real LoanHub loan
  tables; it must NEVER be installed as a production migration.
- A custom PostgreSQL session setting alone is not a secure tenant identity
  against arbitrary untrusted SQL: the application must authenticate staff,
  bind session context only after authorization, use limited DB roles,
  and prohibit user-issued raw SQL.
- SHA-256 hash-chain consistency is tamper-evidence only. An attacker with
  unrestricted historical write access can recompute the chain. Production
  audit requires append-only controls, independent anchoring and verifiable
  off-database evidence.
- Transactional reservation writes from Phase 36 remain disconnected from
  APIs. No live financial posting, disbursement, collections, charges or
  reconciliation can be inferred from passing CI.
- There are NO changes to existing M-PESA integration, shortcode 38542 or
  provider routing.

## Next gate
Before production schema work: inspect actual LoanHub FK model types, tenant
and branch RLS patterns, migration graph, runtime role permissions, audit
requirements, consent and mandate checks. Build an independently reviewed
migration and full PostgreSQL integration suite. Financial posting and
provider-specific callbacks require their own separate signoffs.
