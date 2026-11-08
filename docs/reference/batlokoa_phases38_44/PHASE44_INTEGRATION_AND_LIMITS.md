# Phase 44 — Offline transaction coordinator and integration checklist

## Actual source delivered

`phase44/` contains a complete **synthetic, non-executing transaction coordination example**, tested together with the inherited Phase 35–43 modules:

- `contracts.py`: validated exact LSL cents, borrower/company/loan scope, versioned canonical request fingerprint, mandate and provider-event evidence models.
- `store.py`: standalone SQLite test schema with tenant-keyed uniqueness, provider-event deduplication, journal lines, outbox and audit tables; transaction context manager with rollback.
- `coordinator.py`: idempotent reservation, mandate verification, submission *intent* (never sends a provider request), unknown-outcome classification, settlement/failure/reversal state handling, bound provider events, balanced journal and reversing journal **proposals**, audit and outbox event creation, retry/dead-letter simulation.
- `audit.py`: payload rehash and sequence/link verification for local synthetic audit records.
- `tests/test_phase44.py`: offline end-to-end happy path, duplicate prevention, tenant scope, invalid state transitions, rollback fault injection, provider binding, audit tamper checks, and reversals.

## Integration status — important

**This is not a payment processor.** SQLite is deliberately used as an isolated local simulation. There are no real settlement calls, no HTTP callback endpoints, no actual customer mandates, no financial postings to LoanHub or IthutePay, and no production schema modifications. Evidence model instances can be constructed in test code; real trust requires independently validated, signed/certified provider adapter outputs.

**Do not import these source files as an active web API or run the schema against a live database.** The outbox topic `review.provider.submission` is review-only. A production outbox worker must never reinterpret it as a debit instruction.

## Unfinished production integration coding (must not be fabricated)

1. Map to actual LoanHub company/loan/borrower/branch and accounting models, with lender-approved repayment allocation and mandate rules.
2. Implement a reviewed, real PostgreSQL Alembic migration with composite tenant FKs, restricted database roles, RLS, transactional outbox, immutable journal and audit persistence, and concurrency/rollback integration tests.
3. Implement an IthutePay command endpoint only after authn/authz checks and a verified mandate, plus provider routing that *preserves* existing direct Vodacom M-PESA integration and shortcode 38542.
4. Use the actual provider's documented callback signature/request validation and replay handling; **do not use synthetic HMAC/test attestations** for real money.
5. Integrate settlement proof and financial-book posting with two-sided reconciliation, approved account mapping, refunds, charge policy and dispute/reversal workflow.
6. Run tenant scope, real PostgreSQL concurrency, degraded Redis/provider response, out-of-order callback, timeout-after-provider-accept, late settlement, backup restore, and end-to-end sandbox tests.
7. Require separate product, lender, legal, provider and financial authorization before enabling money movement.

## Test commands

```bash
cd Batlokoa_Phase44_Integrated_Offline_2026-11-08
python3 -m unittest -v tests.test_phase44
python3 run_all_tests.py
```

The bundle also carries three **optional** PostgreSQL tests from earlier phases which **skip** when the explicit disposable test database URL is absent. Passing the other tests does not replace them.

## Release rule

Keep all existing direct M-PESA paths unchanged. Golink is an optional adapter. No production flags, provider credentials, database migrations or remote repositories were touched by Phase 44.
