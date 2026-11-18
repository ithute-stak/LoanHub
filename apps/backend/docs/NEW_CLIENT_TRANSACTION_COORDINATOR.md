# Phase 71 — Verified gate ordering for new-only client creation

This phase introduces `plan_new_only_client_transaction` and
`review_transaction_gate`. The planner validates a server-bound registration
intent and basic client data. The gate uses the existing LoanHub
PostgreSQL transaction locks and normalized collision review.

**Every outcome remains blocked.** Even a clean identity lookup cannot
start registration. Phase 69's idempotency reservation and Phase 70's row
staging are NOT wired to a callable active flow here. The separate modules
are imported only as explicit future integration points. There is no public
route, migration activation, new client account or database commit.

The next safe integration step must prove all of these in a disposable
PostgreSQL database, with real end-to-end integration tests:

1. Exactly one Alembic migration head; Phase 69 table deployed to staging,
   including unique company/idempotency key.
2. Normalized DB uniqueness for national IDs, passports, phone and email,
   subject to legacy collision review and compatibility checks for all
   identity writers.
3. One authorized staff company + branch and one atomic service transaction.
4. Lock identity, guard collisions, reserve idempotency, create **new-only**
   User/Person/Borrower/CompanyBorrowerAccount, finalize reservation, audit,
   then commit once. On any exception, roll everything back.
5. Verify duplicate requests, concurrent branch submissions, failed fees
   and identity collisions without changing loan balances, repayment status,
   borrower banking or historical settlements.
6. Never bypass LoanHub's native permission enforcement or use an existing
   identity linking path in the Batlokoa Flutter application.

**The coordinator does not authorize writes.** Existing historical data
remains untouched.
