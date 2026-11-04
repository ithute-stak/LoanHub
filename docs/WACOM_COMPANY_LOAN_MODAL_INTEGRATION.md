# Wacom test preview — company loan signing dialog

This change mounts the already-developed `ContractPadPreflight` component
inside the **actual** company loan contract modal visible at
`/company/loans`.

A new selection, **Wacom STU-540 (test preview only)**, displays:
- The authenticated contract preflight and test session preparation;
- Cancellation and ongoing eligibility checks;
- The existing local browser handwriting test surface and Wacom
  connector diagnostic status.

While this mode is selected, the existing **Borrower signed** and
**Company signed** actions are hidden, and their underlying handlers
also refuse the preview-only method as a defense in depth. The preview
mode never calls contract signing APIs. Existing Wet ink, Electronic
and Email + OTP signing flows remain available and unchanged.

The contract dialog selects a solid dark title header to avoid the
brand image obscuring the contract number. Other dialogs retain their
existing branded banners.

**Not yet enabled:** An authenticated local Wacom stroke stream,
workstation enrollment and ticket issuance API, identity and consent
verification, encrypted biometric evidence, and signed PDF finalization.
The mouse/touch preview is for disposable tests, not for customer
authorization. Never use "Borrower signed" to test Wacom.

Use a non-customer test contract for preflight verification. This work
requires CI approval and merge before a separately controlled VPS
deployment; merging alone does not deploy production.
