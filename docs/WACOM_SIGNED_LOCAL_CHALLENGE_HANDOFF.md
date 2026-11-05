# Wacom signed-challenge localhost handoff — draft, not activated

The LoanHub workstation-challenge route now requires the preview ticket
signer configuration (disabled by default) and attaches a signed envelope
to each operator-authenticated challenge. The envelope is signed with
Ed25519 and domain-separated from both preview tickets and workstation
proof signatures.

The signed message uses the exact ASCII protocol:
```
LOANHUB-WACOM-CHALLENGE-ENVELOPE-V1
<challenge_id>
<workstation_id>
<session_id>
<nonce>
<unix_expiry_seconds>
```
with a final newline. The backend returns `backend_signing_kid` and
`backend_signature_base64` in addition to the existing challenge fields.

The Go connector validates the backend signature against a separately
operator-provisioned `backend-preview-public-key.json` located beside
`workstation-identity.json`. The key file must be regular (not a symlink),
owned by the connector user, mode 0600, and inside the private, owned
0700 identity directory. Key file example (replace placeholders only
with the approved verified public key, not a private seed):

```json
{"key_id":"approved-kid","public_key_base64":"<approved-32-byte-public-key-base64>"}
```

A backend-signed challenge is necessary before the local Ed25519
workstation key will sign the proof. An arbitrary localhost request,
unverified browser-supplied key, or unsigned challenge is insufficient.

## Local browser adapter

An optional `localWacomChallengeProofHandler` now restricts a single
`POST /v1/preview/workstation-proof` path, exact Origin
`https://loanhub.co.ls`, local Host `127.0.0.1:8765`, CORS preflight,
JSON size limits and rate limiting. It returns only the
`challenge_id`, `workstation_id`, `signature_base64` proof, and
never returns the private key or signs an arbitrary message.

The Contract Signing Centre test panel includes **Get proof from
protected local connector**, which uses that endpoint and then requires
the operator to submit the proof to the authenticated backend
preview-ticket route.

The handler is **NOT mounted** by the running diagnostics service. The
local key and trusted public-key configuration are not provisioned by
this pull request. The full TLS-verified backend introspection, protected
WebSocket mounting, hardware E2E and independent security review must
precede enabling automatic physical capture. A successful unit test
alone does not authorize legal contract signing.
