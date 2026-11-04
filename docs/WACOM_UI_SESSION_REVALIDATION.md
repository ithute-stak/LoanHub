# Wacom — authenticated pad-session UI polling

The existing LoanHub contract preparation UI now polls the authenticated
`GET /contract-signing/contracts/{contract_id}/pad/sessions/{session_id}`
endpoint every five seconds while an operator has a prepared session.

Changes:
- Validates the session and contract IDs returned by the API.
- Requires explicit `capture_enabled: false` and
  `workstation_capture_authorized: false` from the server.
- Shows server-provided eligibility blockers when an agreement is
  edited, locked, signed, expired, cancelled, or otherwise invalidated.
- A failed network request or unexpected response disables test pointer
  capture in that session rather than relying on stale eligibility.
- Cancelling a prepared session clears the locally displayed session;
  unmounting the UI clears its polling interval.
- Browser pointer handwriting remains **local test-only**; the component
  is not connected to signature submission, legal signing or Go USB capture.

An advisory `preview_eligible: true` response is never a workstation
credential or a verified signing approval. The local Go connector is
still restricted to diagnostics-only HTTP status. No preview tickets
or Wacom stroke data are transmitted by this UI.

Remaining: backend authenticated workstation enrollment protocol,
revocation-aware secure transport, connector capture stream and live
browser preview connection. Only after that, separately implement
borrower identity, explicit consent, encrypted evidence and PDF signing.

Existing email-OTP signing remains unchanged.
