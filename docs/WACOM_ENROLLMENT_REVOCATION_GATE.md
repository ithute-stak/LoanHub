# Wacom preview admission — enrolled workstation and revocation gate

This introduces a **pure Go orchestration guard**, not a Wacom HTTP
endpoint, transport implementation, active capture stream or signing
permission.

A future authorized connector caller must supply independent, trusted
implementations of:

1. `previewEnrollmentProvider`: current authenticated, enrolled
   workstation identity, never a browser-asserted device UUID.
2. `previewSessionAuthority`: authoritative backend check for current
   company/operator/contract/session eligibility and revocation.
3. `previewTicketReplayStore`: durable, atomic one-time JTI consumption.
4. Pinned Ed25519 public keys, loaded from protected local provisioning.

Admission requires canonical UUIDs and contract digest, checks workstation
identity, checks backend session eligibility, verifies ticket signature,
purpose, audience, expiry and exact scope, consumes JTI, then checks the
session and workstation again to reduce the revocation race.

A denied post-consumption authorization intentionally leaves the ticket
spent. This service is not an authorization token issuer, and does not
claim a Wacom device or enable browser access.

**Remaining required integration**: authenticated backend check protocol,
workstation enrollment credentials/rotation and revocation, protected
loopback transport, backend signing-session lifecycle and borrower identity,
vendor SDK capture stream, memory-safe browser delivery, cancellation,
audit, encryption and signed-PDF finalization.

CI tests use fake trusted providers, not real backend authorization.
Existing OTP signing and production runtime are unchanged.
