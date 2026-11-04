# Wacom signing preview: admission policy foundation

The physical STU-540 and official Ubuntu SDK were tested with 353
numeric pen reports. LoanHub has a local, in-memory stroke assembler and an
encrypted evidence persistence foundation, but there is **no secure browser
capture transport yet**.

This change adds a private `localPreviewLease` Go primitive:
- Random 256-bit opaque token; maximum 2-minute validity.
- Exact company, borrower, contract, signing-session UUIDs and SHA-256
  contract hash are checked before admitting an ephemeral preview.
- One-time consumption protected by a mutex, replay rejection and revocation.
- No network handler, no serializing raw pen coordinates, no PDF signing,
  no OTP modification or database writes.

**This lease is NOT authentication.** It is insufficient to trust a browser
or to verify hardware identity or borrower consent. Do not mint it from a
public request. The next phase must provide authenticated backend-issued
session authorization, workstation identity, origin/CSRF safeguards, replay
protection, cancellation, bounded transport of pen strokes, and an isolated
preview UI. Explicit user consent and finalization remain separate.

Retain the existing `connected:false` status until a fully reviewed
capture channel exists, and never treat preview approval as loan signing.
