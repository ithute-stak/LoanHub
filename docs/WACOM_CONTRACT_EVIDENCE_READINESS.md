# Wacom — contract-scoped capture evidence readiness

This phase connects the previously verified **client handwriting evidence**
to LoanHub's **existing contract-signing routes** without signing a contract.

## New read-only API

`GET /api/v1/contract-signing/contracts/{contract_id}/pad/verified-capture-evidence`

The request must use the existing authenticated LoanHub tenant context. The
existing `_contract` guard verifies that the requested contract belongs to
the selected company and that the employee has branch access.

Only file metadata is returned for capture evidence which:
- Belongs to the same LoanHub company as the contract.
- Is linked to the **exact borrower ID on that contract**.
- Was independently reviewed as a verified Wacom client capture.
- Has clean malware scan results and encrypted/confidential private storage.
- Has not been marked deleted.

No raw PNG bytes, storage keys, pen coordinates or unrelated borrowers are
returned. The response explicitly says `can_apply_capture_to_document:false`,
`automatic_signature_reuse_enabled:false`, and
`requires_fresh_contract_consent:true`.

## Existing signing controls remain authoritative

This phase **does not** write or modify `BorrowerSavedSignature`,
`BorrowerSignatureUseAuthorization`, `ContractPadSigningSession`,
the loan contract hash, contract PDF, or borrower signature timestamp.
Existing contract preflight blockers remain visible.

A verified capture means the image was reviewed, not that the borrower has
approved a specific agreement. LoanHub must still confirm the exact contract
version/hash, borrower identity, specific informed consent, a valid nonexpired
session and a per-contract authorization before anything can be signed.

## Next engineering gate

Implement contract-specific signed consent evidence and atomic finalization
using LoanHub's existing contract-signing services, **not** a new VPS bridge.
Before activation test full PostgreSQL row-level isolation and run the
physical STU-540 workflow on the real employee PC.

No deployment is performed by this change.
