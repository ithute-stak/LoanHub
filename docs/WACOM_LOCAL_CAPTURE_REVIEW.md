# Local Wacom capture evidence review — no automatic document signing

The **PC runs the Wacom pad** and sends an encrypted captured PNG directly
to LoanHub's existing FastAPI backend. LoanHub persists it as a private,
pending-review `ManagedFile`. This change adds independent evidence review
through existing LoanHub tenant/company management permissions, not a new
service or staging backend.

## Review endpoints (existing backend)

- `GET /api/v1/local-signatures/review`: metadata of pending captures
  **only for the authenticated manager's selected company**.
- `GET /api/v1/local-signatures/review/{file_id}/preview`: decrypt and
  stream one clean, encrypted PNG for authorized company management,
  with no-store headers; not exposed publicly.
- `POST /api/v1/local-signatures/review/{file_id}/decision`: atomically
  verify or reject a pending capture, requiring an independent reviewer
  (not the upload operator) and a recorded reference and reason.

Example **test-data-only** verification body:

```json
{
  "decision": "verify",
  "identity_checked": true,
  "consent_checked": true,
  "evidence_reference": "MANUAL-ID-CONSENT-123",
  "reason": "Signer identity and capture consent independently reviewed"
}
```

Reject with `"decision":"reject"`, including a meaningful reason; no
identity/consent check is mandatory when rejecting.

## What does 'verified' mean?

It means the reviewer attested to checking the **capture evidence**, not
that the signature can be used to sign a document.

The operator status endpoint and the tenant-scoped client lookup now return
`verified_capture` when review is complete, or `pending_review` before
review, and `missing` when neither exists. If a genuine
`BorrowerSavedSignature` from an approved contract signing session already
exists, the client status may be `active`. Only such separately authorized
signing records may participate in the existing contract workflows.

No review endpoint creates `BorrowerSavedSignature`, modifies a loan,
generates a PDF, consumes signature evidence for a contract, or permits
automatic reuse. Any use of stored handwriting in a specific agreement
must go through the existing borrower-verified, per-contract consent and
authorization mechanism.

## Review conditions

- Valid, active company staff management authorization
- The pending capture must belong to the reviewer's company
- Same user cannot upload and approve their own evidence
- Capture must be encrypted, confidential, private and cleanly malware scanned
- Signer kind and owner links must be valid
- Explicit identity and consent check confirmations for verification
- State change plus audit record in the same database transaction
- No raw signature bytes in review metadata or audit logs

The original capture file remains encrypted in LoanHub storage. Review does
not give the local PC permission to sign a contract.

## Before any production enablement

Verify real PostgreSQL migrations/RLS behavior, real company/branch access,
ClamAV clean scanning, encryption keys, audit integrity, physical STU-540
capture, identity evidence and explicit signer consent. Keep these changes
in draft until both code review and integration tests are successful.

No separate Wacom VPS bridge is involved.
