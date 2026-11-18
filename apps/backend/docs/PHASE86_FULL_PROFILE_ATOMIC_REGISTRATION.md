# Phase 86 — Full-profile atomic new-client registration (internal)

This phase integrates the previously disconnected full-profile staging helper
inside the **same** protected `create_new_client_atomically` PostgreSQL
transaction. It introduces `create_full_new_client_atomically` as an
internal callable, **not** an exposed FastAPI route.

The complete validated request is hashed for the idempotency fingerprint;
no employer, debt or bank field is omitted from that fingerprint. Only the
mandatory core identity fields are projected for the already-approved
new-only Person/User/Borrower insertion. After the new-only reservation is
confirmed to be **new** and base account staged, the remaining full-profile
fields are staged using exactly the same Session and `db.begin()` scope.
Only then is the idempotency reservation finalized.

If employee authorization, identity uniqueness, historical passport/ID
collision, payment-fee snapshot, bank encryption, external debt staging or
finalization fails, PostgreSQL rolls back all new rows. Replayed completed
requests return the prior scoped account without reinserting debts or
bank accounts. Existing borrowers are NEVER linked or modified.

The Phase 85 field restrictions still fail closed: credential/email
creation, employer-group changes, CDAS linkage and unsupported purportedly
verified financial data are not silently accepted.

## Evidence and pending approvals

Real isolated PostgreSQL integration tests create synthetic staff, new
identities, company accounts, optional employment records and declared
external debt obligations. They check correct amount/status preservation,
idempotent retry and all-record rollback from a simulated failure after
new identity creation.

This phase does not implement an API route or production feature flag and
does not install the four normalized uniqueness indexes. Independent banking
encryption, debt reconciliation and deployed-schema tests must be completed
before any production activation. A DBA-reviewed real-data uniqueness
migration and independent operational approvals are still required.

No existing LoanHub calculator, repayment, loan settlement or historic
client records are altered.
