# Batlokoa LoanHub → IthutePay — Phase 31 Integration

This change connects the existing Phase 30 tenant/borrower authorization
service to the Phase 29 signed **read-only** IthutePay collection preview.

## Endpoint

`POST /api/v1/loans/{loan_id}/batlokoa/collection-preview`

Request: `{"amount":"100.00","idempotency_key":"collect_req_A123456789"}`.

The existing LoanHub tenant-authenticated `get_tenant_context` dependency
resolves an active user, selected company and role. The service derives
borrower identity through a company-filtered database query, calls the
Phase 30 authorizer for loan, membership, branch, status and amount checks,
then invokes the existing body-bound HMAC-signed IthutePay preview client.

The caller cannot supply a borrower, company, merchant, shortcode, provider
credentials, phone, or execution flags. No financial record is created,
updated or committed.

## Production gating

Both flags must be separately approved before a preview can operate:
- LoanHub `ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED=false` (default)
- IthutePay `LOANHUB_BATLOKOA_INTENT_PREVIEW_ENABLED=false` (default)

Do not enable these flags merely because CI passes. The existing
production **handshake** remains independent. Do not change Vodacom M-PESA
shortcode 38542 or existing provider adapters.

## Critical limitation

This endpoint **only previews**; success is not a borrower debit mandate.
Idempotency keys are not persisted or reserved. A successful preview does not
guarantee the loan balance stays unchanged between the read and any future
payment. A future financial stage requires a new, independently reviewed
transactional design including explicit mandate verification, database
locking, unique tenant-scoped idempotency, provider callback verification,
reconciliation, fee agreements, RLS isolation and audit evidence.

The Phase 33 offline payment lifecycle and PostgreSQL reservation prototypes
are retained in the user's review ZIP and are **not** registered as models,
migrations or executable financial services. They should only be reviewed
in a separate, future-activation pull request.

## Verification

Tests cover anonymous access, forbidden caller-controlled identity fields,
disabled-gate no-op behavior, company scoping, validated borrower lookup,
unsafe upstream response rejection and generic transport error handling.

Do not deploy until normal CI and integration contract tests pass.
