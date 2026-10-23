# LoanHub CDAS Phase 1 — DataNet third-party API v1.5 contract audit

Source: user-provided **CDAS LS API Doc for Third Party API**, version 1.5, February 2024 (27 pages). This is a restricted, non-binding reference; do not redistribute the underlying document. Findings below describe the public application source, not live CDAS connectivity.

## Endpoint inventory

| Operation | Document endpoint | LoanHub client | Initial result |
| --- | --- | --- | --- |
| Login | `/api/security/login` | `CdasClient.authenticate` | Path and documented Username/Password/Authorization contract present |
| Employee | `/api/employee/getDetails` | `get_employee_details` | EmployeeNo and documented fields parsed |
| Affordability | `/api/employee/check-affordability` | `check_affordability` | Numeric value converted to Decimal |
| All deductions | `/api/policy/view-all-deduction` | `view_all_deductions` | Array validation present |
| Own deductions | `/api/policy/view-deduction` | `view_own_deductions` | EmployeeNo and DeductionStatus sent |
| Add/update/review/approve/cancel | `/api/policy/add-update-deduction` | `add_update_deduction` | Payload model present |
| Active/approved | `/api/policy/get-active-and-approved-deduction` | `get_active_and_approved_deduction` | Object validation present |
| Modify active | `/api/policy/modify-active-deduction` | `modify_active_deduction` | Payload model present |
| Settle | `/api/policy/settled-deduction` | `settle_deduction` | Payload model present |
| Documents | `/api/policy/get_document` | `get_document` | Year/Month/DocumentType and FileName/Content support |

## Findings and follow-up

1. **P1 — HTTP 406 overloaded.** Document pages 22 and 19 use 406 for both report-not-ready and invalid token format. `CDAS_PROVIDER_ERROR_CATALOG[406]` unconditionally classifies it as an auth failure. Error interpretation should be endpoint- and payload-aware, and document-not-ready should remain an ordinary business/transient outcome, not a credential reset.
2. **P1 — success response validation may be too permissive.** `CdasDeductionRecord` has mostly optional fields, allows extra fields, and `validate_deduction` returns the original dict. Introduce endpoint-specific validation of required identifiers on write confirmations, while retaining raw payload for audit and testing historically sparse read responses.
3. **P1 — monetary and status data semantics.** Provider `ReducingBalance` is not necessarily LoanHub's paid/reconciled balance. Do not mark LoanHub payments posted solely from registered or approved deductions. Audit existing payment-posting boundaries.
4. **P2 — documentary ambiguities.** Page 25 reuses code 6 for Reject/Cancelled and 8 for Auto-settled/Expired. Preserve numeric provider codes and request an authoritative status-transition table. Page 22 spells `DocumentTye`; parser currently supports this typo, confirm whether provider returns `DocumentType` instead.
5. **P2 — token handling.** Login token 8h, idle 10min; LoanHub proactively uses 7h50m/9m. Read-only calls may reauthenticate and retry. Mutation paths use `retry_expired_session=False`, appropriate for avoiding duplicate writes. Keep mock tests for both outcomes.
6. **P2 — rate limits.** Document says 400 calls/day/API user. Existing `cdas_request_budget.py` tracks per username/environment using an atomic DB counter and Lesotho day. Verify effective credential tenant mapping and concurrent-worker behavior in integration tests; account for login attempts and provider-side limit responses.
7. **P2 — employee number is not national ID.** `getDetails` accepts `EmployeeNo`, not national ID; matching to LoanHub identities must use verified demographic fields and authorization, not guesswork.
8. **P2 — read/live evidence gap.** Source-level endpoint presence is verified; actual CDAS HTTP interoperability, permissions, provider schema variants and sample statements have **not** been tested. Live testing must use authorized sandbox/test credentials and redacted fixtures.

## Recommended test matrix before production changes

- 200 body shape for each of the ten endpoints, including empty list, sparse optional fields, numeric amounts, and documents.
- 401/402/419 token/session expiry on read; 406 invalid-token versus 406 not-ready distinction.
- 429, 495–499 provider failures with exact action-specific feedback.
- All write paths: no automatic replay on timeout, token expiry or uncertain provider result; reconcile provider state first.
- 400/day request budget across backend workers and matching CDAS login accounts.
- Negative tenant authorization cases and sensitive employee-data redaction.

## Phase 1 status

**Initial static audit complete, provider contract conformance unverified.** No production CDAS request sent. This document is an audit baseline, not acceptance of the live integration.