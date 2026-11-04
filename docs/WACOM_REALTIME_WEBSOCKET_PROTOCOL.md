# LoanHub Real-Time Wacom Signature Engine — WebSocket Protocol v1

## Objective

Provide a reusable WebSocket-based **test handwriting preview** for LoanHub forms while preserving all existing contract signing methods. This is a separate implementation track from #579 (proof-bound backend ticket), #580 (cancellable SDK source), and #581 (HTTP preview transport).

**Current branch contents:** a browser-only hook and a reusable, unmounted field component. The connector does **not** expose a WebSocket route yet. Real contract signing is still disabled.

## Proposed endpoint

`ws://127.0.0.1:8765/v1/preview/stream` — same loopback Go service and systemd unit. No external listener; do not route this connection through loanhub.co.ls VPS. Browsers accessing an HTTPS application may require additional local-network permission or a secure-loopback transport; test this in deployment Chrome before activation.

The server **MUST** reject every upgrade unless:
- Exact `Origin: https://loanhub.co.ls` and `Host: 127.0.0.1:8765` match.
- All WebSocket upgrade prerequisites are valid and the connection has short idle/read/write deadlines, frame limits, ping/pong and an explicit close policy.
- The backend authorizer verifies the signed, audience-limited preview ticket (sent in the first WebSocket message, never URL, headers or logs), exact company/operator/document-hash/session/workstation/field binding, an active enrolled workstation, atomic one-time replay prevention, live revocation and document consistency **before** starting SDK capture.
- The browser's `field_id` is only an untrusted selector. It cannot authorize capture or choose a tenant/session by itself.
- A global per-device capture lock prevents competing tabs, sessions and SDK subprocesses.

## Browser-to-connector messages

`{"type":"authorize_preview","preview_ticket":"...","field_id":"borrower_signature"}`
`{"type":"cancel"}`

Only send `authorize_preview` after the user selects the field and deliberately clicks Start; focus alone cannot trigger SDK capture. All actual authorization must be obtained through the backend using workstation proof and current borrower consent.

## Connector-to-browser messages

All emitted messages must contain exact `session_key` and `field_id` matching the browser's active backend-approved session. These are context labels, **not proof** of authorization.

`{"type":"authorized","session_key":"...","field_id":"..."}`

`{"type":"preview_strokes","session_key":"...","field_id":"...","strokes":[[{"x":123,"y":45,"at":12,"pressure":0.4}]]}`

`{"type":"complete","session_key":"...","field_id":"..."}`

`{"type":"revoked","session_key":"...","field_id":"..."}`

`{"type":"expired","session_key":"...","field_id":"..."}`

The connector must send **cumulative, validated stroke snapshots**, not unbounded raw SDK reports. Respect the existing `validateWacomPreviewStrokes` 640×240 constraints, avoid point loss between frames, throttle broadcasts, and cap frame sizes. The existing browser hook rejects malformed, oversized and cross-session messages.

On cancellation, tab close, ticket expiry, backend revocation, contract switch or device disconnect: interrupt SDK capture, release device lock, clear transient pen buffers and canvas, close the socket. Never persist raw strokes or turn `complete` into signature approval.

## Required server-side follow-up

1. Integrate #579 backend ticket issuance with #578 workstation challenge-response; pin signing keys and implement durable token replay consumption.
2. Implement server WebSocket upgrade and first-message admission, using the trusted backend authorizer from #581 (not client-derived IDs).
3. Adapt #580 cancellable SDK pen source for incremental stroke updates with revocation checks during idle pen periods, not only pen arrivals.
4. Mount `WacomSignatureField` into the existing contract modal and other explicitly registered fields. Do not auto-enroll every element with `id="signature"`.
5. Run server Go tests, frontend TypeScript checks, and a physical STU-540 end-to-end demonstration on Selemela before activating feature flags.

This protocol is not evidence retention, contract PDF stamping, or a legally binding electronic signature mechanism.
