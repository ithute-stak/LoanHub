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

## 2026-11-19: database-login-anchored authorization experiment

`test_document_issuance_authenticated_lock_login_postgres.py` opens a
**separate authenticated PostgreSQL TCP connection** using a disposable login
role with no direct protected-table privileges. A SECURITY DEFINER test
function resolves its allowed tenant from an owner-controlled mapping keyed
by PostgreSQL `session_user`, not `current_setting('loanhub.company_id')`.
The test attempts cross-tenant GUC impersonation and demonstrates that the
function only allows the tenant mapped to the login. It also tests direct
SELECT/UPDATE denial.

This is **not** a final production approach. A single shared application
database login would represent *all* tenants, so mapping that login to a
tenant would not establish a user-specific membership or staff permission.
Provisioning per-tenant database credentials may be operationally complex
and requires lifecycle, rotation, revocation, connection-pool isolation,
and role-inheritance auditing. Do not reuse a server-side privileged login
from untrusted tenant request handling. A trusted issuer-authentication
service or appropriately isolated capability is still required, followed by
real integration tests against production-equivalent role grants and RLS.

## 2026-11-21: ORM identity-cache revocation hazard

The non-routed `require_current_document_issuer` gate now requests
`populate_existing()` for User, LoanCompany, and CompanyStaff queries, so an
earlier-loaded SQLAlchemy object cannot silently supply an outdated role or
activation status after the database query. This is a defense-in-depth
point-in-time verification, **not a transaction-wide lock**.

The remaining time-of-check/time-of-use race is explicit: a membership may be
revoked after that query but before issuance commits. Neither repeating a
query without serialization nor trusting a tenant GUC closes the race.
Before deployment, an approved trusted issuer service must hold an appropriate
authorization guard through commit, or use an equivalent verified
revocation-safe capability. The existing experimental direct FOR SHARE path
continues to require privileges unavailable to SELECT-only SQL sessions.


## 2026-11-21: final commit-boundary issuer recheck

The non-routed generic locked-document registration now rechecks persisted
issuer activation, approved company and exact staff membership after ledger
and audit flush, immediately before SQL COMMIT. If the second recheck observes
revocation, the transaction rolls back and no issued PDF is returned.
Regression coverage injects revocation between the two checks.

**Still BLOCKED:** concurrent revocation can occur after the final read but
before COMMIT because neither read holds compatible row locks for the entire
transaction. An approved independently authenticated issuer transaction and
real PostgreSQL revocation/issuance concurrency tests are required. Do not
mistake additional point-in-time checks for serialization, do not grant broad
UPDATE privileges, and do not enable the spoofable SECURITY DEFINER prototype.


## 2026-11-21: isolated PostgreSQL revocation-lock proof

The real-PostgreSQL source-lock test suite now also covers the three issuer
authorization rows (user, company, staff) in disposable test tables. It
acquires `FOR SHARE NOWAIT` locks in the issuer transaction, verifies that
a second connection's revocation UPDATE fails with lock timeout SQLSTATE
`55P03`, and verifies revocation succeeds after the issuer transaction ends.

This proves PostgreSQL locking mechanics only. It **does not** show that
production issuance holds these locks, or that a SELECT-only app role can
acquire them. Real deployment still requires a separately authenticated,
narrowly privileged issuer design that handles lock ordering, privilege
revocation, transaction ownership, timeouts and RLS without tenant GUC spoofing.


## 2026-11-21: revocation-first PostgreSQL concurrency scenario

The isolated PostgreSQL issuer-lock suite now verifies both orders:

- **Issuance locks first:** a concurrent revocation cannot change user,
  company or staff rows until the issuer transaction releases its locks.
- **Revocation updates first:** a new issuer `FOR SHARE NOWAIT` fails with
  SQLSTATE `55P03`; once revocation commits, a fresh authorization lock
  query finds no active row.

These tests are prerequisite evidence, **not a connected production issuer**.
Production must prove the authorization guard spans final COMMIT with a
separately trusted SQL identity, correct RLS permissions, robust handling of
timeouts, and all signing/source integrity checks before any public route.
