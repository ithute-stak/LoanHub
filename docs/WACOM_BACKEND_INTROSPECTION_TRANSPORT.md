# Wacom connector: authenticated backend session introspection

This branch introduces `hardenedWacomIntrospectionClient` as a **transport-only**
building block. It is not registered in the running diagnostics connector,
nor does it implement `backendWacomPreviewResolver`.

## Fixed request

`POST https://loanhub.co.ls/api/v1/wacom/connector/preview-introspect`

JSON body: `{"preview_ticket":"<short-lived proof-bound ticket>"}`

- Requires TLS 1.3, pinned backend CA, and a locally provisioned client
  certificate/private key; neither comes from a browser request.
- Rejects redirects, URL parameters, alternate hosts and HTTP downgrade.
- A missing backend endpoint, invalid credentials or malformed response fails
  closed. The API route **does not exist yet** and must not be assumed live.
- Ticket never appears in URL, request headers, logging or persistent state.
- Response is capped at 16KiB; it contains a scope *snapshot*, not authorization
  by itself.

## Server-side requirements before implementing the resolver

1. Authorize an approved, non-revoked enrolled workstation using verified
   mutual-TLS client identity and independently stored enrollment records.
2. Independently load the active session and contract with tenant/operator
   authorization, current document hash, exact signing field and consent.
3. Verify the Ed25519 preview ticket, audience, purpose, company, operator,
   contract, document digest, workstation and session; never trust browser
   values or parsed claims alone.
4. Return current scope only over `Cache-Control: no-store`. Protect against
   token replay and rate-limit all requests.
5. Implement **separate live revocation and durable single-use ticket consume
   providers** on the connector, backed by authoritative server state.
   A snapshot cannot replace those services. No local fake/in-memory replay
   store is acceptable.
6. Keep SDK executable pinned to an independently configured local path.
   A server response is not authorization to execute software.
7. Do not enable `/v1/preview/stream` until browser cross-origin and secure
   localhost policy, back-to-back revocation, transport errors, cancellation,
   and physical STU-540 E2E tests pass.

The STU-540 diagnostics process and existing contract signing modes remain
unchanged. No handwriting evidence or signed document is created.
