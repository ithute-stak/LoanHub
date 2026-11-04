# Wacom STU-540 localhost preview HTTP bridge (staging-only foundation)

This PR implements a **dependency-injected** `POST /v1/preview/capture` adapter returning ephemeral calibrated strokes. The route is **not registered** by the current diagnostics-mode server: `GET /v1/device/status` remains the only live route. Production signing remains disabled.

## Request / response

`POST http://127.0.0.1:8765/v1/preview/capture` from the exact `https://loanhub.co.ls` Origin with JSON `{"preview_ticket":"<short-lived server-issued ticket>"}` and Content-Type application/json.

A verified, enrolled workstation and backend-derived scope are mandatory. The HTTP adapter **never** trusts a browser-supplied company, contract, workstation or session identifier, and requires an injected `previewCaptureAuthorizer` to resolve current scope and provide pinned ticket verification keys, a durable replay store, revocation authority, real calibration and an approved SDK capture source. The existing coordinator verifies the Ed25519 ticket and rechecks revocation before returning any strokes. A successful response carries `{"purpose":"test-preview-only","strokes":[...]}`, never a signed document.

Data remains in process memory until JSON encoding finishes. No persistence, evidence upload or legal signature endpoint is added. Any failure returns no strokes. HTTPS-to-loopback browser permissions and authorization must be validated in Chrome.

## Before enabling the route

1. Review and merge the backend proof-bound preview ticket implementation (#579) and cancellable SDK source (#580) after CI.
2. Implement a **real** authenticated workstation authorizer that revalidates operator/tenant, current contract hash, enrolled workstation, replay and revocation. It must not derive trust from decoded unverified ticket fields.
3. Build a verified browser challenge-response exchange, protect ticket handling (never in URL/storage/logs), and have the frontend render the response with `WacomStrokePreview` only in its active matching contract session.
4. Deliberately register the preview HTTP adapter in a separate explicitly enabled mode; adjust HTTP server write timeout for the bounded capture while preventing multiple concurrent SDK sessions.
5. Test USB hot-unplug, mid-capture cancellation, expired/replayed tickets, cross-tenant scope, session/contract changes and browser canvas cleanup on Selemela with the physical STU-540.

Do **not** expose this listener on `0.0.0.0`, reverse-proxy it, or enable signature finalization as part of this integration.
