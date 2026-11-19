# Batlokoa — Future durable application idempotency (NOT ACTIVATED)

This is a design document for the isolated offline development branch. The
only implemented code in this iteration is **pure, no-write** HMAC request
canonicalization and replay classification. No live writer, migration, public
route, or loan-application reservation is connected.

## Proposed durable PostgreSQL state

A reviewed migration would introduce a separate
`new_only_application_attempts` table with:

- UUID primary key and `company_id`, `branch_id`, `employee_user_id`,
  `account_id`, `borrower_id` UUID foreign keys
- `request_key` (16–128 characters) and `request_fingerprint` (64-character
  lowercase HMAC-SHA256 hex), neither containing client identity strings
- `status` strictly `reserved`, `completed` or `rejected`
- `application_id` nullable FK to `direct_loan_applications`, a server-side
  completion timestamp and reviewed audit columns
- `UNIQUE(company_id, request_key)` to make replays deterministic across
  browser retries
- `UNIQUE(account_id)` or an equivalent approved new-only-first-application
  constraint to guarantee a single application per newly registered account;
  do **not** enforce this on existing clients or historical applications
- DB-level `CHECK` constraints for completed states requiring an
  application ID, and reserved states prohibiting one

These are **proposed** constraints: their compatibility with the real LoanHub
schema, tenant RLS, existing index names, row ownership and migration
rollback must be reviewed before any Alembic change is written.

## Proposed transaction sequence

1. Authenticate active, approved company membership; verify branch scope
   and permission inside the current PostgreSQL transaction.
2. Acquire global account advisory lock in the same transaction. All
   participating application writers must use one protocol.
3. Verify completed new-only registration provenance, normalized identity,
   cross-source history and pending registration prerequisites.
4. Verify active tenant loan product, amount and term limits, current KYC,
   affordability inputs and lending policy.
5. Insert the `(company_id, request_key)` reservation with
   `ON CONFLICT DO NOTHING`, then `SELECT ... FOR UPDATE`.
6. Compare constant-time HMAC request fingerprints and staff/account/branch
   identity; reject mismatches, in-progress and previously rejected keys.
7. Re-query all origination/legacy exposure within the same transaction.
   Before activation, certify that all other origination writers cannot
   bypass duplicate-application protections.
8. Only when separately authorized, create **one** new draft application
   using existing LoanHub policy and calculator components unchanged.
   Persist the linked completed idempotency record and audit event with the
   draft in one transaction, then commit atomically.
9. Any exception rolls back all newly inserted records; no historical
   borrower, existing loan, payment or settlement can be modified.

## Current implementation boundaries

`services/batlokoa_new_only_application_idempotency_design.py` provides a
pure HMAC fingerprint of scoped IDs, normalized money and term. It excludes
borrower name, ID number, phone, passport and bank data. Reusing a request key
with a changed company, branch, actor, client, product, amount or term yields
a mismatch. Matching replays of any status return only a **no-new-write**
decision. No function reserves anything or authorizes application creation.

`services/batlokoa_new_only_application_lock_review.py` is a separate
internal, read-only cooperative advisory-lock preflight. It neither
persists request keys nor protects concurrent existing writers. These
properties must not be presented as durable idempotency.

## Required before merge/release

- PostgreSQL test container migration upgrade/downgrade rehearsal
- Concurrent processes: same account/different keys; same key/different
  payload; independent companies; rollback and interrupted transactions
- Every origination writer inventory and consistent lock/unique enforcement
- Cross-source historical borrower/loan collision audit
- Product/credit/KYC policy and full end-to-end branch permissions testing
- Independent DBA, data steward, security and Batlokoa business sign-off

This offline design is **not production-ready** and is not an instruction
to create a migration or deploy to the VPS.
