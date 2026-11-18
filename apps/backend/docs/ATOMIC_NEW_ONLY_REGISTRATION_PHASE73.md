# Phase 73 — Internal atomic new-only registration (not exposed)

This change introduces the first *callable*, strictly **internal** LoanHub
registration transaction, `create_new_client_atomically`. It is not a
FastAPI endpoint, is not connected to Batlokoa's staff application, and has
no production activation configuration.

## One-transaction ordering

1. Validate `AssistedCompanyClientCreate` and reject fields unsupported by
   this restricted first writer (employment details, bank, debts, payroll,
   salary, email, non-default nationality and client-supplied passwords).
   Never silently discard data.
2. Construct a verified LoanHub staff/company/branch intent with a keyed
   fingerprint of the *complete* request and an idempotency key.
3. Reject an already-running SQLAlchemy transaction; open a dedicated
   PostgreSQL transaction owned by the caller's session.
4. Inspect PostgreSQL system catalogs for the four precisely named, valid,
   ready and unique normalized national ID/passport/phone/email indexes.
   **No index DDL is included**; the indexes are not yet deployed.
5. Acquire deterministic global identity advisory locks and run normalized
   Person/User/tenant-legacy collision checks.
6. Reserve `(company_id,idempotency_key)` atomically and verify replay
   fingerprint, employee and branch. Existing completed requests only return
   after checking the actual account belongs to the same scope.
7. Reject historical national-ID captures **across all companies**, without
   exposing any other company's borrower or loan information.
8. For a new, clear identity, stage a *new* User/Person/Borrower/account and
   audit event in one SQLAlchemy session. Apply existing account opening fee
   configuration, rather than zeroing configured fees.
9. Finalize idempotency to `completed` only after verifying the new
   account belongs to the same tenant, branch and employee.
10. Let the `with db.begin()` transaction commit **once** on success or
    roll back all steps on any exception.

No old user, borrower, loan, repayment, bank record, settlement status or
historic capture is updated by this new-only service.

## Why production remains unavailable

The required *normalized unique indexes have not been created*. Existing
identity writers, historical normalized duplicate groups and privacy
safeguards must be audited. The service is not reachable from any API.

This initial internal writer intentionally supports only a minimal client:
the current production assisted schema contains banking, external debts,
salary, employer and payroll fields which must not be discarded. Those
submissions are rejected until the full workflow is implemented.

The internal staging helper's `approved_internal_call` argument is NOT an
authorization control; the orchestration must be reachable only from
verified server-side code after proper LoanHub RBAC, branch authorization,
KYC and schema readiness. Re-run both unit tests and isolated PostgreSQL
concurrency, schema and rollback checks before any new deployment.

**Do not execute this path against production databases.** The required
unique index migration, staff-API authorization, borrower credential
delivery, data protection review, no-account-update invariant integration
and safe staged rollout remain future work.
