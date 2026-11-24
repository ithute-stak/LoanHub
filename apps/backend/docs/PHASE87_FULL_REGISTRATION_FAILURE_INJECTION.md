# Phase 87 — Real PostgreSQL full-registration fault-injection checks

Phase 85 and 86 are merged into main with passing CI. This phase extends
the isolated PostgreSQL tests for the **internal** full-registration method.

The tests inject failures at three separate boundaries of the same
transaction: the encrypted-bank capture helper, after the real external
debt and debt-event rows are inserted, and at idempotency finalization.
For every injected failure they verify that no new Person, User, Borrower,
company account, registration attempt, audit entry, bank account, debt
obligation or debt event remains committed.

Tests then retry the **same idempotency key** with the original payload
after the injected fault is removed, proving that failed registration
attempts do not poison retry state or create duplicate debts.

These tests run only against a disposable `*_sandbox` PostgreSQL database
and synthetic clients. They never connect to production data.

No public registration endpoint, client creation UI or identity-index
migration is enabled. Existing LoanHub loans, settlements, calculator and
payment logic are unchanged.
