# Phase 69 — Durable new-client registration request idempotency

New database model and *review-only* Alembic migration:
`new_client_registration_attempts` with unique
`(company_id,idempotency_key)`. The record retains company, branch, employee,
complete-request keyed HMAC fingerprint, reserved/completed/rejected status,
optional new client account ID, and timestamps. Raw client IDs (national ID,
passport, phone), salary, bank details, and loan data are not stored in the
idempotency table.

An internal `reserve_new_client_registration` helper inserts a request key
with PostgreSQL `ON CONFLICT DO NOTHING`, then reads the tenant/key under
`FOR UPDATE`, comparing the full fingerprint, branch, and actor to prevent
a conflicting replay. The database uniqueness constraint decides between
concurrent reservations; application-level preflight alone is insufficient.

Reservation requires a caller-owned PostgreSQL transaction and **never
commits**. The remaining lifecycle completion function always raises an
exception; no new borrower, person, client or loan can be created by this
module. No new API endpoint or feature flag is enabled.

## Rollout blockers

- Migration review and real database staging exercise, including unique
  constraints, schema head resolution, downgrade and rollback.
- A complete new-only registration writer that creates exactly one User,
  Person, Borrower, CompanyBorrowerAccount, audit event and completion
  of the attempt inside **one atomic transaction**, with no reused person.
- Verified normalized national ID/passport, phone/email uniqueness across
  all relevant identity writers; inspected legacy collisions.
- Idempotent concurrent replay, nonretryable rejected status, expiry/cleanup,
  session revocation, and client-side no-double-submit behaviour.
- Cross-tenant/branch RBAC, historical loan invariants and explicit
  operator sign-off in isolated PostgreSQL staging.

**Do not deploy the migration automatically or use this to authorize
registration.** Batlokoa's registration button remains disabled.
