# Wacom STU-540 — proof-bound backend preview authorization

The verified physical SDK pen test on Selemela collected 824 SDK reports,
473 contact points and 8 strokes. The production browser currently only
detects the local diagnostic server; **no pen strokes reach the web page.**

This phase adds a new authenticated FastAPI endpoint:

`POST /api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/preview-tickets`

Request:
```json
{"workstation_id":"<approved UUID>","challenge_id":"<unused challenge UUID>","signature_base64":"<Ed25519 challenge signature>"}
```

This request must be performed by the logged-in, tenant-scoped LoanHub
operator who owns the exact existing unsigned-contract preview session.
The endpoint checks current contract eligibility, locks contract and session,
verifies an approved unrevoked enrollment, verifies the backend-issued 30s
Ed25519 possession challenge and consumes it atomically, and then issues a
30-second Ed25519-signed, single-purpose, contract-hash-bound preview ticket.
The response is no-store and returns `capture_enabled:false`.
It NEVER signs a PDF, records consent, or receives pen coordinates.

## Fail-closed deployment settings

This feature is **disabled by default**. All three settings must be explicitly
provisioned in a controlled staging environment:

- `LOANHUB_WACOM_PREVIEW_TICKETS_ENABLED=true`
- `LOANHUB_WACOM_PREVIEW_SIGNING_SEED_B64`: canonical Base64 of 32 random
  Ed25519 private-seed bytes (secret: never commit or print)
- `LOANHUB_WACOM_PREVIEW_SIGNING_KID`: approved pinned key identifier

The corresponding public key must be configured separately as a trusted key
on the Go connector; do not take the public key from a browser parameter.

## Critical unfinished components

This is an incremental authorization step, **not** a complete fix for
physical Wacom pen-to-browser streaming. Do not activate the feature on
production until the following are implemented and demonstrated:

1. Protected local device private key, two-person enrollment approval,
   and authenticated Go-to-backend challenge exchange.
2. Pinned backend public-key trust on the connector, one-use replay store,
   authenticated, independently backend-verified session and enrollment
   revocation authority, and start/stop SDK source.
3. An authenticated, origin-restricted localhost capture transport and
   session-scoped browser preview. Pen data must not be sent to LoanHub or
   retained as signing evidence. Cancellation/expiry immediately clear it.
4. TLS/CSRF/origin and token-redaction review, rate limiting, concurrent
   revocation and PostgreSQL integration tests, and physical pad testing.
5. Separate borrower identity, consent, encrypted evidence and final PDF
   signing flow before any legally binding capture.

Existing wet-ink, electronic, email-OTP and in-browser pointer preview
methods remain unchanged. Production default stays disabled.
