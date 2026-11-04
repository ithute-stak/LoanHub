# Wacom — authorized, ephemeral pen-preview orchestration

The STU-540's physical USB enumeration and calibrated local stroke tests
have already succeeded on Selemela. The production LoanHub contract
modal also sees the local diagnostics connector. **That is not yet an
authenticated physical handwriting stream.**

This phase adds a **pure, dependency-injected Go preview coordinator**.
It is not a browser route, WebSocket, network listener, signing API or
production capture feature.

The coordinator requires:
- A previously enrolled workstation identity provider and current,
  backend-backed signing-session authority.
- Pinned Ed25519 backend verification keys and durable, atomic one-use
  replay protection.
- A valid signed `test-preview-only` ticket tied to the exact company,
  operator, contract digest, session and workstation.
- An explicitly supplied SDK pen source, whose implementation must stop
  when its context expires or is cancelled.
- An authenticated in-memory browser preview sink.
- Vendor-reported calibration; no forged browser calibration.

It verifies admission **before** invoking the SDK. Capture is bounded
to at most 20 seconds and the signed ticket's remaining validity, whichever
is shorter. The pen callback checks revocation at least every 500ms
**while reports are arriving**, and the coordinator also checks before
and after capture and immediately before delivery. If authorization
changes, no points are delivered; captured native points are discarded
from the local buffer on return. The sink must never save handwriting.

The code does NOT claim immediate revocation during an idle SDK source:
that requires the future transport's cancellation push mechanism, plus
server-backed enrollment and revocation adapters. The existing
`testWacomSampleWithHandler` command is a local CLI diagnostic and is
not mounted as an HTTP capture source.

## Still required before browser handwriting can appear

1. Privileged, audited workstation enrollment approval and durable
   challenge creation/verification endpoints.
2. Verified workstation private-key provisioning, revocation and
   protected authenticated backend channel.
3. A context-cancellable, bounded SDK pen-source adapter.
4. Authenticated, contract- and session-scoped browser transport with
   origin checks, cancellation propagation, replay and rate limits.
5. Integration tests of active cancellation and expiry, on the physical
   STU-540 and the real browser.
6. Separately approved identity verification, explicit borrower consent,
   encrypted evidence and signed-PDF finalization for legal signatures.

Until those are implemented, **only local diagnostics and mouse/touch
test-preview are available**. Existing email-OTP signing is unchanged.
