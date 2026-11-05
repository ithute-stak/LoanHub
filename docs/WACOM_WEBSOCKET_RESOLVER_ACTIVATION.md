# Wacom WebSocket — scope resolver and activation gates

The Go `mtlsWacomPreviewResolver` now bridges the fixed HTTPS introspection
client to `verifiedWacomWebSocketAuthority`:

1. HTTPS client fetches current scope using pinned TLS CA and local mTLS
   workstation client certificate.
2. Resolver checks canonical UUIDs, strict contract hash, locally pinned
   workstation ID, signed ticket, fixed borrower field and session identity.
3. Resolver injects *separately provided* local trusted signer keys, live
   workstation enrollment authority, live session revocation authority,
   durable atomic replay store, verified vendor calibration and local SDK path.
4. Authority validates the signed ticket and live eligibility once more.
5. The coordinator performs the final atomic replay consume, pre-SDK
   enrollment/session checks and periodic checks while the SDK runs.

The resolver does **not** scrape identity from the ticket or browser, choose
an SDK binary from remote JSON, or manufacture a local replay store.
A successful introspection response alone never authorizes physical capture.

## Still deliberately unavailable

- Verified mTLS ingress identity injection into FastAPI `request.scope`
  is not implemented. No `X-Forwarded-Client-Cert` or arbitrary browser header
  must ever be trusted as workstation proof.
- No production live `previewSessionAuthority` or
  `previewEnrollmentProvider` is yet wired to the backend.
- No configured durable `previewTicketReplayStore` has been wired.
- WebSocket handler remains **unmounted** in the running diagnostic service.
- The contract signing modal has not been wired to the component.
- Browser HTTPS-to-localhost WebSocket behavior and physical SDK E2E
  capture are not verified on the Selemela workstation.

**Activation rule:** leave feature flags false and legal signing disabled
until all of the above are solved, tested, and independently reviewed.
