# Wacom preview — durable single-workstation replay admission

The existing `filePreviewReplayStore` on `main` is now selected by
`newProtectedWacomPreviewAuthority`, instead of leaving the replay
dependency entirely caller-supplied.

- A pre-provisioned local directory must be absolute, owned by the connector
  service account, mode `0700`, and a real directory (not a symlink).
- `ConsumeOnce` hashes the JTI, creates the replay marker with
  `O_CREATE|O_EXCL`, and syncs both the file and directory. Concurrent
  callers on the same filesystem cannot consume the same ticket twice.
- The replay marker persists across process restarts. It is not removed
  automatically; use an offline, expiry-aware retention procedure.
- Missing or insecure storage fails closed. No in-memory replay-store
  fallback is installed by the production-intended factory.
- This implements **single-workstation** replay defense only. When the
  same ticket could be accepted by more than one independent host, use a
  centrally atomic replay store before production enablement.
- The factory does **not** install HTTP routes, enable SDK capture,
  initialize client certificates, or provision signer keys. The existing
  `loanhub-wacom.service` remains diagnostics-only.

## Remaining activation blockers

The trusted ASGI TLS server extension must be supplied from a real mTLS
handshake; certificate revocation handling and key rotation must be tested;
the connector must be provisioned with trusted certificate materials,
locally pinned SDK path and public signer key, live backend revalidation,
vendor SDK calibration, and private replay storage. Then mount the guarded
WebSocket route in a test-only service, integrate the browser signature
field, and complete physical STU-540 end-to-end testing.

Never treat a passing unit test as proof of legal signing functionality.
