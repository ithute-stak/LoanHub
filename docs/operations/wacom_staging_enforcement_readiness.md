# Wacom first-party PC bridge — staging enforcement readiness

Status: **engineering test plan; NOT a deployment record or authorization to enable signing**.

## Exact security boundary

The existing `/api/v1/local-signatures/*` routes are guarded by
`LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION=1`. When this variable is absent
or different from `1`, those routes continue their previous LoanHub
membership-based authorization and DO NOT enforce a workstation proof.
Changing IP address does not grant or revoke LoanHub workstation identities.

The local Go bridge requires `--pc-ui --workstation-key-dir=<absolute private 0700 directory>`
for its device-key login mode. Without the key directory, it can still start in
legacy mode and DOES NOT hold a workstation bridge credential.

**Neither flag should be enabled until production-safe gateway policy, backend
migrations, approved workstation enrollment, employee assignment and
full test coverage are verified.**

## Staging activation sequence (only in isolated Wacom staging)

1. Confirm the deployed container image SHA, staging-only domain and the
   instance-specific database. Do not run a migration against the shared
   production LoanHub database without an approved deployment plan.
2. Confirm Alembic revisions through `c2d3e4f5g834` are applied to
   the staging database. Take and verify a restorable staging backup.
3. Create a dedicated test company and synthetic employees/borrower. Approve a
   workstation key via the existing company-admin workflow; assign at least
   two test operators. Never use real customer signatures as fixtures.
4. Provision the workstation identity directory with owner-only 0700
   directory and 0600 key file. Keep private seed on the local machine.
5. Confirm HTTPS outbound from the bridge only to the authorized staging API.
   Restrict staging edge routes, TLS, request size, login rate limits,
   telemetry and abuse protection independently from workstation admission.
6. Enable `LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION=1` in the **staging backend
   container only**. Verify process-effective environment, not only a
   compose file.
7. Run the access matrix. Require denial for every negative case below.
8. Revalidate after app/container restart, workstation disconnect, altered
   public IP, token expiry, operator switch and employee revocation.
9. Leave contract signing, borrower signature reuse and live loan disbursement
   disabled. Capture receipt stays `usable_for_signing: false`.
10. Record redacted test outcomes, timestamps, container SHA and reviewer
    acceptance before any decision to enable beyond controlled staging.

## Negative tests (required)

- Anonymous and borrower-only user: denied.
- Valid staff password, but no workstation assignment: denied.
- Assigned staff on unapproved/revoked PC: denied.
- Correct PC key, wrong company/user/nonce: proof denied.
- Malformed, missing, expired, previously revoked bridge credential: denied.
- Token issued for employee A used by B: denied.
- Old credential after employee revocation or workstation revocation: denied.
- Direct API call with LoanHub staff bearer but **without bridge session**:
  `/local-signatures/me/status`, `/clients/lookup`, `/captures` all denied.
- Rotating public IP does not change the authorization decision.
- Local operator switch clears previous person's borrower, captured
  handwriting and session data.

## Known limitations before production readiness

- The five-minute credential is an in-memory **bearer** capability after
  device proof, not a signature on each API call. Access-token theft is still
  a risk; keep local process, OS permissions and TLS hardened.
- The opt-in guard is scoped to the local-signatures router, **not all LoanHub
  lending APIs**. Loan origination remains governed by its existing separate
  permissions, not by this Wacom session.
- Independent `/local-signatures/review` routes are separate and are not
  covered by the current local-signatures router dependency. Continue
  management-role, independent-review and evidence safeguards and assess
  whether review should require a workstation session.
- A company owner selecting an employee for provisioning must never be able
  to impersonate that employee. Signing a specific document requires
  explicit consent/authorization and tamper-evident version binding.

## Abort and rollback

If a positive case is rejected, verify the staging-only key, time synchronization,
company assignment, approved enrollment, backend revision and session header.
If ANY unauthorized request succeeds, STOP deployment; do not turn off
monitoring to suppress the failure. Disabling the staging flag restores
legacy behavior but is NOT a security-safe state for external exposure.
Re-isolate staging at its gateway or take the Wacom endpoint offline.

Do not infer green status from a code-merged or CI-passed PR; gather
separate real staging evidence before activating customer workflows.
