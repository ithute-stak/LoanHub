# Contract signing centre — Wacom preview UI integration

The real LoanHub `ContractPadPreflight` now includes a Wacom test preview
field, after the operator prepares a pad signing session, **only** when the
frontend build-time flag `NEXT_PUBLIC_LOANHUB_WACOM_PREVIEW_UI=true` is set.

The new field is deliberately **disabled**. It displays an inactive preview
surface within the actual contract workflow but cannot generate a preview
ticket, invoke the local STU-540 capture socket, or submit signing evidence.
Its authorization callback always rejects. This is a UI composition step
only, not functional hardware capture.

The backend ticket issuer presently requires a backend-approved workstation
possession proof. The browser cannot generate that proof: the enrolled
private key must stay on the authenticated workstation. Do not send the
private key to JavaScript or substitute an unsigned ticket.

Before enabling the field, implement the challenge/proof exchange through
an authenticated, trusted local workstation channel. Integrate that exchange
with backend ticket issuance, bind the approval to the exact company,
operator, contract digest, signing session, workstation and
`borrower_signature` field, then validate hardware end-to-end.

The existing browser pointer-signature canvas is unchanged. Existing
wet-ink, electronic, Email + OTP, and company signing paths are unchanged.
Neither this UI flag nor the field authorizes contract execution.
