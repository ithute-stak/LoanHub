# Wacom: independent legally operative signing ceremony — integration requirements

This policy is NOT a legal finding and NOT a signing endpoint.

**Existing workflow:** original PDF -> independent handwritten-evidence review ->
two-person archival approval -> separately approved field -> encrypted final PDF
candidate -> independently verifiable candidate receipt.

**A further, distinct ceremony is required before any borrower contract is marked
signed.** The archived candidate alone must never modify `LoanContract` status.

Integration requirements:

1. Generate a new server-side, single-use challenge bound to the exact candidate
   SHA-256, the company, borrower, contract, workstation and approved field hash.
2. Obtain a new explicit borrower affirmative decision after showing the exact
   document, with an independently recorded timestamp and reference. Do not
   reuse the earlier handwriting-capture consent.
3. Independently verify the STU-540 workstation/device challenge cryptographically,
   tenant authorization, hardware presence and associated evidence.
   Setting `signature_verified=True` without verification is forbidden.
4. Obtain a separately evidenced, legally reviewed release for the applicable
   jurisdiction and signature type, approved by an independent authorized
   individual; do not treat visible PDF ink as a PKI digital signature.
5. Re-read and verify all immutable source, evidence and candidate bytes, then
   re-check contract version, tenant, hashes, independence and single-use state.
6. Under repeatable transaction locks, record the legal execution result and
   signed document reference, consume the one-time permit, and advance the loan
   contract **only if** independent legal and end-to-end acceptance tests pass.
7. Protect against double execution with a durable unique operation key, and
   implement recovery for uncertain database-commit and object-storage states.
8. Do not enable production until the actual Wacom-equipped workstation has
   passed physical end-to-end tests and the applicable legal acceptance criteria
   have been formally approved.

`execution_ceremony_blockers` is a **pure denial policy** over separately
verified inputs. No API creates these fresh ceremony records yet. Its empty
list is not a grant to sign; it is one prerequisite for a future reviewed
transaction. Do not enable Wacom execution based on these tests alone.
