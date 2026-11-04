# Signed preview-only Wacom authorization tickets

A physical STU-540 completed the local calibrated diagnostic: 206 SDK
reports, 50 contact points, two strokes and 50 validated preview points.
That proves the local hardware pipeline only—not application signing.

This phase adds a *pure, backend-only* Ed25519 ticket issuer. The caller
must independently authenticate the operator, verify the workstation
identity, retrieve the tenant-scoped persisted pad session and canonical
contract record, and run the backend admission policy before issuing a
ticket. Tickets have:
- EdDSA Ed25519 signature and configured key identifier
- exact company/operator/contract/session/workstation identifiers
- immutable contract SHA-256 digest
- explicit `test-preview-only` purpose and connector audience
- random `jti`, issue time, max 60-second expiry, capped by session expiry

**Not yet implemented:**
- HTTP endpoint issuing tickets after database authorization and device
  enrollment; key management and rotation
- Go connector verification using a pinned public key and authenticated
  workstation identity; backend revocation check
- Durable atomic single-use `jti` replay prevention across connector
  restarts, browser session lifecycle and secure short-lived streaming
- Browser display of authenticated physical pen strokes
- Borrower identification, per-contract consent, encrypted evidence
  finalization, audit and signed contract PDF.

This issuer MUST NOT be called directly with unverified browser values.
Do not deploy a signing endpoint on the basis of this module. The
existing email-OTP signing path stays unchanged.
