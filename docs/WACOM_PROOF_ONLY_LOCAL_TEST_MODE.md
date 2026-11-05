# Wacom STU-540 — explicit proof-only localhost testing

The Go connector now has a separate `--preview-proof-test` mode, which
composes the **existing** diagnostics status route with the restricted
`/v1/preview/workstation-proof` handler. It does **not** mount
`/v1/preview/stream`, read tablet pen reports, sign contracts, or submit
handwriting. Normal `--diagnostics` still runs its original status-only
handler.

## Preconditions for local development

- A dedicated test workstation must have its own approved Ed25519 identity
  in an existing, connector-owned, 0700 directory containing the private
  `workstation-identity.json` (0600).
- The independently approved backend Ed25519 verification key must exist
  beside it in `backend-preview-public-key.json` (0600), with fields
  `key_id` and `public_key_base64`. Never put a private key in this file.
- The backend must explicitly enable preview-ticket signer configuration
  **only in staging**. This mode does not override its feature flags.
- Stop any *test* process already listening on 127.0.0.1:8765 before
  starting this mode. Never interrupt a production systemd service just
  to try these instructions.

Run a standalone test-only connector binary on the enrolled workstation:

```sh
./loanhub-wacom --preview-proof-test=/secure/wacom-test-identity
```

Verify that `GET http://127.0.0.1:8765/v1/device/status` works and that
`GET /v1/preview/stream` returns 404 (no capture). The browser's
`NEXT_PUBLIC_LOANHUB_WACOM_PREVIEW_UI=true` mode can request the backend
challenge and exchange it at the local proof endpoint after the operator
has prepared a currently eligible contract session.

The proof handler admits only an exact localhost Host, exact authorized
HTTPS Origin, CORS preflight for POST JSON, limited request size, trusted
backend-signed short-lived challenges and a locally pinned verification
key. No general-purpose signature route or private-key export exists.

**Limitations:** this is a protocol-testing adapter, not a completed
hardware preview. Localhost Origin headers can be spoofed by non-browser
clients, so deploy only on a controlled trusted workstation and conduct
an independent security review before exposing the service to users.
There is no WebSocket capture endpoint in this mode. Full live mTLS
certificate verification through the actual TLS terminator, end-to-end
STU-540 SDK streaming and borrower consent/finalization remain separate
gates. Neither test proof nor test preview constitutes a legal signature.
