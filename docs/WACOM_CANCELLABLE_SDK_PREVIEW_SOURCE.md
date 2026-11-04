# Wacom STU-540 — context-cancellable official SDK pen source

The standalone physical hardware test on Selemela passed with 824 SDK
reports, 473 contact points and 8 calibrated strokes. But that local
diagnostic does not reach the LoanHub browser.

This change adds `wacomSDKPreviewSource`, a concrete dependency for
`runEphemeralAuthorizedPreview` (PR #573). The SDK source:
- Refuses nil/expired/unbounded contexts and unsafe SDK executable paths.
- Uses the existing known-working official `simpleInterface` PTY parser.
- Propagates request cancellation into the vendor process to stop sampling.
- Collects for at most 10 seconds, reserving at least 2 seconds for final
  active-session / revocation revalidation and in-memory preview delivery.
- Does not create HTTP routes, touch signing databases, store coordinates,
  modify PDF contracts, or bypass the signed ticket admission coordinator.

The test's previous 25-second behavior is retained for local CLI diagnostics.
The preview source is deliberately **not mounted** until the backend-to-local
workstation proof exchange and signed-ticket verification are connected to
the authenticated localhost preview transport and trusted revocation checks.

Before release:
- Test on physical STU-540, cancellation during an active SDK read, hot-unplug,
  and multi-process USB contention on Selemela.
- Make revocation push immediate even with no pen reports.
- Wire safe lease admission, strict browser origin checks, durable replay
  protection and a temporary `WacomStrokePreview` renderer.
- Clear browser preview on expiry/cancel/contract switch.
- Preserve existing wet ink, electronic, email OTP and test pointer methods.

No physical SDK pen stream is exposed to the internet by this PR.
