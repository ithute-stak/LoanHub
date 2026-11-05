# Wacom connector client identity: mTLS ASGI bridge

## Implemented

`WacomVerifiedMTLSIdentityMiddleware` is installed in the LoanHub FastAPI
application. For the connector-only `/api/v1/wacom/connector/preview-introspect`
route, it discards any preexisting workstation identity field on the ASGI
scope and, only with opt-in configuration, maps a verified client TLS
certificate to a pinned workstation UUID.

Required settings (default to **disabled**):

- `LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED=true`
- `LOANHUB_WACOM_MTLS_CERT_PINS_JSON={"<workstation-uuid>":"<sha256-lowercase-DER-leaf-cert>"}`
- `LOANHUB_WACOM_PREVIEW_VERIFY_KEY_B64` and
  `LOANHUB_WACOM_PREVIEW_SIGNING_KID`, pinned separately to backend
  ticket signing key configuration.

## Important deployment prerequisite

This middleware **does not terminate TLS**. It cannot independently know
whether an HTTP client actually presented a valid certificate. The
application's **trusted ASGI TLS-terminating server/integration** must
populate `scope["extensions"]["tls"]` with:

- `client_cert_verified: True` from a real mTLS handshake with server-side
  certificate chain validation and client authentication;
- `client_cert_chain` containing the actual client leaf certificate as
  DER bytes, first, extracted from that authenticated handshake.

The above two attributes are a **deployment integration contract**, not a
claim that standard Uvicorn or a reverse proxy provides them automatically.
Do not enable the feature until an actual trusted server adapter implements
and tests this exact contract. Client-supplied HTTP headers such as
`X-SSL-Client-Cert`, `X-Forwarded-Client-Cert` or
`X-Verified-Workstation-ID` are not accepted. Ingress must prevent any
untrusted actor from injecting the ASGI TLS extension.

Certificate fingerprints are pinned as deployment secrets and checked after
the upstream mTLS-verification flag. Rotating or revoking a certificate
requires an explicit pin update/revocation. Fingerprint pinning alone does
not replace authoritative enrollment/session revocation.

## Still blocked

- Protected deployment and validation of TLS server ASGI scope adapter.
- Actual authenticated Go-live-session / enrollment authorities and durable
  one-use ticket replay store.
- Enabling workstation SDK capture, browser field mounting and physical
  device E2E validation.

Keep the opt-in flag unset, and preserve existing signing routes and the
working systemd Wacom device diagnostics service until these gates pass.
