# Borrower saved signatures — security contract

LoanHub may offer an opt-in signature vault scoped to a company and a borrower.
A saved handwritten signature **is not a reusable legal authorization**.

## Data and rules
- `borrower_saved_signatures`: metadata, immutable evidence digest, encrypted-object reference,
  capture provenance and opt-in/revocation status. Do **not** store an unencrypted PNG,
  coordinates or dynamic biometric pen data in database columns.
- `borrower_signature_use_authorizations`: one specific company, borrower,
  saved profile, signing session, contract ID and immutable contract hash.
  Identity verification and express approval must occur for **each** contract.
- A signature captured on a pad cannot be saved for later use without a
  separately recorded opt-in explaining retention, revocation and purpose.
- A new contract/revision requires a new session and a new authorization;
  an expired, revoked or cross-company profile must fail closed.
- Never auto-apply a stored signature based on borrower name, user ID,
  PDF position or an existing loan.
- The future signing endpoint must recheck the record under a row lock,
  consume authorizations exactly once, finalize the exact approved PDF and
  write a permanent audit record in one controlled workflow.
- Deleting a signature profile must revoke future use while preserving
  lawfully required contract audit evidence under a documented retention policy.

## Delivery status
This change adds schema and reusable-signature authorization policy tests only.
No API for writing signatures is enabled, because secure Wacom capture, verified
identity, encrypted object storage, explicit consent and PDF finalization have
not yet been wired. Existing email-OTP signing paths are unchanged.
