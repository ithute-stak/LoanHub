# CDAS sandbox verification — operator acceptance checklist

**Scope:** Authorized CDAS *test* environment only. Do not use real employee data or perform financial mutations without written provider authorization, approved test records and a rollback/reconciliation plan.

## Entry requirements

- [ ] Platform Owner has the correct company identifier and the provider-issued **test** base URL, username and password, supplied through the secure admin interface (never through code, logs, GitHub issues or chat).
- [ ] Provider has confirmed test environment access, test employee numbers and allowed calls.
- [ ] Relevant company's subscription has been approved if required by the LoanHub CDAS profile workflow.
- [ ] A current LoanHub release image has passed CI and has been deployed through the established approval process. Record the deployed SHA.
- [ ] Name a test operator and date/time of each call, along with an incident contact.
- [ ] Request budget and provider rate limits have been checked.

## Read-only steps

1. As Platform Owner, save the company's CDAS **test** profile at `PUT /platform-owner/cdas/companies/{company_id}/profiles/test` through the authorized admin interface. The server encrypts the stored password. Verify response does not reveal credentials.
2. As Platform Owner, run `POST /platform-owner/cdas/companies/{company_id}/profiles/test/test` once. This invokes `CdasClient.check_connection()`, which authenticates via `/api/security/login`. Record success/failure and `last_tested_at`, not session tokens. **Do not interpret success as verification of deductions or affordability.**
3. Only after explicit provider permission, use a designated test employee for read-only `/api/employee/getDetails`, `/api/employee/check-affordability`, and `/api/policy/view-all-deduction`. Verify employee number agreement, zero-affordability handling and no accidental production records.
4. Verify read-only reporting and deduction status using provider-approved test fixtures. Reconcile differences manually; preserve response status and correlation IDs without credentials or unnecessary personal data.
5. If login fails or the provider environment is ambiguous, **stop**. Do not switch to Live as a workaround.

## Separate financial-write approval gate (not covered by this checklist)

- [ ] Provider explicitly authorizes test registration/approval/modification/settlement and supplies designated test identities.
- [ ] Operator confirms the exact company, employee, deduction identity, amount and requested lifecycle status.
- [ ] Every state-changing operation uses the tracked mutation ledger and cannot be automatically retried after a timeout or ambiguous acknowledgement.
- [ ] Reconciliation verifies employee, deduction identity and expected status before confirming. A pending operation must not be resubmitted.
- [ ] All affected test records are reconciled or formally documented as unresolved after testing.

## Evidence to retain

Record tenant/company ID, environment=`test`, deployment SHA, test operator, date/time, operation category, HTTP result, redacted provider correlation ID, whether expected data/status matched, and whether any operation requires reconciliation. Never retain passwords, authorization headers, session tokens, national IDs, or complete employee payloads in tickets.

## Exit decision

- **Pass — read-only sandbox**: authenticated test profile and authorized employee/affordability/deduction reads succeed with consistent identities.
- **Blocked**: no authorized sandbox profile, no approved test employee or insufficient provider permission.
- **Fail**: authorization, identity, payload validation or reconciliation problem. Keep Live disabled until resolved.

Automated tests such as `test_cdas_phase12_sandbox_connection_smoke.py` use mocked HTTP responses. They do **not** satisfy the live-sandbox evidence requirement.
