# Draft: Trust boundary for locked signed-contract issuance

**Status: BLOCKED — not a deployment specification.** No public issuance route
may call the experimental signed-contract registration flow yet.

## Proven observations

- The application can prove that a LoanContract refers to a particular loan,
  version, frozen terms hash and current generated ManagedFile. These checks
  must happen again at registration, not only during S3 Object Lock staging.
- PostgreSQL `SELECT ... FOR SHARE NOWAIT` does not work for an ordinary
  SELECT-only role: it requires additional table locking privileges, including
  UPDATE privilege. Broad UPDATE grants on financial or contract tables are
  not an acceptable shortcut.
- A narrowly granted SECURITY DEFINER function can execute row locks on
  behalf of a SELECT-only caller. That **does not by itself make it safe**.
- A caller allowed to execute SQL under the common database application
  identity can set arbitrary `loanhub.company_id` and `loanhub.actor_scope`
  custom settings. This can cross tenant boundaries if the privileged function
  treats the settings as identity proof. See
  `test_document_issuance_lock_identity_spoof_postgres.py`.

## Required security decisions before implementation

1. Choose a trust anchor independent of untrusted client-supplied tenant
   settings: e.g. an isolated server-only privileged signing/locking component
   whose credentials are not available to normal application sessions, with
   independently checked authenticated issuer and tenant membership.
2. Define *narrow* capabilities: only an authorized, existing signed and locked
   LoanContract with matching borrower, approved loan, exact ManagedFile ID and
   version can be locked. Record borrower/company signatures and contract hash.
3. Keep privileged credentials out of normal application connections. Revoke
   PUBLIC EXECUTE and audit role inheritance, function ownership, search_path,
   SQL injection surfaces, and the ability to create temporary shadow objects.
4. Prove a single transaction holds all source locks through immutable version
   validation, stamp approval recheck, issuance ledger INSERT and COMMIT.
   Include genuine concurrent updates and cancellation/timeout tests.
5. Deny use on missing/expired/cancelled authorization, changed stamp,
   changed contract version, changed PDF bytes, revoked signatures or wrong
   tenant. Verify role grants with a real non-owner, NOBYPASSRLS runtime user.
6. Keep object-version retention, S3 IAM/COMPLIANCE and source storage
   immutability as independent gates. A relational lock does not lock the
   external PDF object or guarantee a PDF's legal semantics.
7. Audit every attempt, failure and uncertain commit, and reconcile
   outstanding locked S3 versions before retry or release.

**Do not deploy the existing proof-of-concept SECURITY DEFINER SQL.** Its
company setting can be spoofed. The tests establish privilege mechanics and
the failure mode; they do not certify production tenant authentication.

The current implementation is intentionally non-routed and must remain in a
draft PR until the security design and separate runtime-role tests pass.
