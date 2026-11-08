# Phase 38–41 integration plan: staged changes, not applied

The supplied files are **offline contracts**, intentionally unrelated to the
running API's import graph. Nothing here changes `main`, Alembic, Docker,
production environment variables or loan balances.

## Phase 38 — Audit and durable state

- Review the existing merged Phase 36 reservation core and Phase 37 RLS tests.
- Create a reviewed migration, mapping to LoanHub's actual company, loan and
  borrower FK constraints. Make company ownership a composite FK boundary.
- Add optimistic version check in `UPDATE ... WHERE version=:expected`, row
  locking, unique provider event IDs, transactional event+outbox insertion.
- Use restricted SQL roles, RLS and audit anchoring outside the writable DB.
- Prove crash recovery and races on disposable PostgreSQL.

## Phase 39 — Financial posting

- Obtain approved company repayment policy (including legally applicable
  charges, interest and duplum policies) and posting account mappings.
- Implement a single locked DB transaction: verified settlement evidence,
  company/loan ownership, allocation, balanced journal, unique posting key,
  loan balance update, audit and outbox. Roll back every write on any failure.
- Explicitly implement separate approved overpayment and refund policies.
- Verify double posting and cross-tenant financial isolation under concurrency.

## Phase 40 — Provider and reconciliation

- Do not replace existing M-PESA adapter or assume third-party credentials.
- Implement a separate, certified adapter per provider; never register the
  synthetic test provider as a live one.
- Durable callback signatures/nonce verification, duplication protection,
  late/partial/unknown outcomes, provider query, settlement-file matching.
- Escalate mismatches to an exception queue, not automatic money movement.

## Phase 41 — Staging certification

- Record exact staging image SHA, TLS and host controls, synthetic test loans,
  isolated PostgreSQL and Redis, secrets and connection allowlists.
- Execute pre-flight safety flags disabled; verify old direct M-PESA paths.
- Test signed and forged requests, RLS cross-company, outage recovery,
  duplicate callbacks, rollback, backup restore, log redaction and concurrency.
- Obtain legal, finance, security and operational approval with evidence IDs.
- A successful offline test or CI build **is not** payment authorization.
