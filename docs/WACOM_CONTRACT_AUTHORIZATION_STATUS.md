# Wacom: document-specific signature authorization inspection (Phase 8)

This phase adds a read-only status check to the **existing LoanHub
contract-signing router**. The local Wacom connector remains on the PC.

## Endpoint

`GET /api/v1/contract-signing/contracts/{contract_id}/pad/use-authorization-status`

The existing authenticated employee authorization and company/branch
contract guards apply before inspecting saved-signature records.

The status check requires an exact match across:
- LoanHub company, contract and borrower IDs
- Current contract hash and present PDF
- Active, unrevoked saved borrower signature
- Explicit contract-specific authorization, not already used or cancelled
- Verified identity and consent timestamps
- Matching, unexpired consenting/captured signing session
- No previous borrower signing or contract locking

If any check fails, a generic blocker code is reported. No image, raw
handwriting, secret key or biometric data is returned.

## Security boundary

This endpoint cannot approve the borrower, grant consent, create an
authorization record, upload a signature, generate a PDF or sign the
contract. Even if `eligibility_checks_passed` is true, it is only a
read-only snapshot; a future signature-use implementation **must**
re-evaluate every condition under database row locks inside the same
atomic transaction that finalizes the contract.

The existing `BorrowerSignatureUseAuthorization`,
`BorrowerSavedSignature`, and `ContractPadSigningSession` models
are reused. No new service or database table is introduced.

## Remaining before live signing

Implement verified, tamper-evident borrower consent bound to the exact
contract version and hash; borrower-controlled authorization and
revocation; atomic PDF finalization with audit and race-condition tests;
and physical workstation testing with the installed STU-540.

Keep draft PRs unmerged until CI, PostgreSQL tenant tests and legal
approval are complete. No production deployment is part of this change.
