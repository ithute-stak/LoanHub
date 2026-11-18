# Phase 81 — Revalidate staff authorization in the registration transaction

A previously valid LoanHub staff session can become stale after the employee
is disabled, transferred to another branch, or their lending membership is
revoked. Checking the login context only before entering PostgreSQL is not
sufficient to protect the new-only client creation boundary.

Phase 81 adds a fresh `CompanyStaff` and `User` membership check **inside
the exact database transaction** that creates a new client. It:

- Requires exactly one active company lending staff membership for the
  authenticated user, with an active `users` row.
- Requires non-management lending staff to match the *current* assigned
  branch. A null or transferred branch fails closed.
- Takes PostgreSQL shared row locks on staff and user rows, so concurrent
  revocations cannot silently race a new-client write.
- Performs these checks before branch lookup, advisory identity locks,
  idempotency reservation, borrower staging or audit events.
- Adds unit regressions for disabled, ambiguous or branchless membership,
  plus an isolated actual PostgreSQL test that revokes the membership after
  a first registration and rejects a second operation without extra rows.

The earlier Phase 76 context validation still runs; Phase 81 intentionally
rechecks persisted authorizations to close stale-session windows. The
production client-registration API, schema-index migration and Batlokoa
registration button remain disabled. No historical financial data is
altered.
