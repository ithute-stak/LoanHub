# Wacom STU-540 — isolated browser preview renderer

The physical calibrated Go diagnostic now passes on the Ubuntu STU-540:
206 SDK pen reports, 50 contact points, two strokes and 50 valid
transformed preview points. **This does not yet constitute a real
contract signature.**

The Next.js frontend now contains a reusable `WacomStrokePreview` React
canvas component. It accepts **only prevalidated temporary preview
points** in LoanHub's 640×240 coordinate space. In the component itself:

- `active` defaults to false and rendering is denied without a session key.
- All points must be finite, in bounds, time-ordered, pressure [0,1],
  with at most 300 strokes, 10,000 points and 120 seconds.
- Invalid inputs, inactive status and session changes clear the canvas.
- No `fetch`, localStorage, signature data URL, persistence or finalization
  code is included.
- The renderer is **not mounted into live contract signing flows yet**.
  This prevents browser-origin or operator-provided data from being
  mistaken for verified Wacom signing evidence.

Remaining before real display of physical Wacom handwriting:
1. A backend-verified company/borrower/contract/session authorization,
   including contract version/hash and explicit test-only state.
2. Authenticated, non-replayable, strictly scoped loopback connector
   communication and short-lived stream lifecycle.
3. Verified SDK device provenance, trustworthy mapping of reported
   capabilities, cancellation and memory expiry.
4. An integration test connecting a real authorized workstation
   preview stream to the existing contract-preflight screen.
5. Separate verified borrower identity, consent, encrypted evidence
   finalization, PDF signing and auditing before activating real signing.

Do not wire this component directly to unauthenticated browser messages,
unverified WebSocket events, or arbitrary localhost services. Existing
email-OTP signing and production LoanHub functionality are unchanged.
