# Wacom local connector — signed preview ticket verification

Local SDK capture was physically verified with 206 reports, 50 contact
points, two strokes and 50 calibrated preview points.

This PR adds a **pure Go verifier** for future, backend-issued,
Ed25519-signed `test-preview-only` tickets.

What it enforces:
- Pinned Ed25519 public key selected by trusted `kid`
- Signature over the exact compact token header and payload bytes
- Fixed preview audience and purpose
- Valid issue/expiration timestamps, <=60 seconds, no future use
- Independently supplied company/operator/contract/hash/session/workstation
  scope; never trust the token itself as source of expected identifiers
- Required durable atomic one-time JTI consumer interface; nil, replay
  or store outage must fail closed

**Integration deliberately NOT enabled**: there is no HTTP route, no
public key installed by default, no workstation identity enrollment, no
persistent JTI store implementation, no server-side revocation check,
no captured-stroke transmission and no contract signing changes.

Future backend and connector entrypoints must implement enrolled
workstation authentication, protected local transport, durable replay
storage (e.g. Redis atomic SET NX with expiry), revocation, rate limits,
short-lived capture lifecycle and cancellation before exposing a stream.

These checks alone are not equivalent to a legal signature. Borrower
identity, consent, encrypted evidence and signed PDF finalization
remain separately gated.
