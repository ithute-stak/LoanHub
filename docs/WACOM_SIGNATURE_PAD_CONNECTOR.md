# LoanHub Wacom STU native connector protocol (design contract)

This phase adds **browser detection only**. It does not include a native daemon,
Wacom vendor SDK binaries, capture over USB, signature submission, or contract finalization.

## Browser check

The browser explicitly requests `GET http://127.0.0.1:8765/v1/device/status`
when staff press "Detect Wacom pad". A compatible local connector should return:

```json
{"protocol":"loanhub-wacom-v1","connected":true,"model":"STU-430","firmware":"optional"}
```

The endpoint conveys diagnostic status only. It is never evidence of identity,
borrower consent, or authority to sign.

## Native connector requirements (not yet implemented)

- Use the official SDK matching the physical Wacom model and host OS.
- Bind only to 127.0.0.1; reject other Host and Origin values.
- Allow only the exact authorized LoanHub HTTPS origins through CORS,
  with proper browser private-network permissions where applicable.
- Resist DNS rebinding and cross-site request forgery. Do not expose
  unauthenticated capture endpoints to arbitrary local/browser clients.
- Pair the connector with a short-lived backend-issued signing session,
  exact contract UUID/version/hash, authenticated operator and verified
  borrower consent. Never accept a browser-supplied contract hash as proof.
- Avoid persistent raw pen data in the daemon. Encrypt any retained
  signature evidence. Add replay protection and session expiry.
- Stop acquisition on cancellation, disconnection and contract switching.
- Server must atomically validate and commit the signed PDF and audit record.
- No existing wet ink or email OTP signing endpoint may be used to smuggle
  unverified pen captures into a completed agreement.
- Validate browsers' mixed-content/private-network restrictions; a loopback
  HTTP service may require a trusted HTTPS loopback endpoint in production.

## Next implementation

Build the native bridge and a server-backed signing session before enabling
real capture. Verify the actual Wacom model, Ubuntu/Windows host and SDK
licensing/capabilities with the vendor.
