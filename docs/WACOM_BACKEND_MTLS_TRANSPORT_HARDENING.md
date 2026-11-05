# Wacom protected preview — backend mTLS transport hardening

The protected Go preview authority constructor now calls
`hardenedWacomIntrospectionClient.securelyConfigured()` before it can
build the authenticated WebSocket preview authority.

This change blocks a missing or generic HTTP client from being injected
into the protected preview configuration. Configuration is refused unless:

- The endpoint is exactly
  `https://loanhub.co.ls/api/v1/wacom/connector/preview-introspect`
  (no URL parameters, credentials, alternative hosts or fragments).
- The HTTP transport is a TLS-configured `*http.Transport`, using TLS
  1.3 minimum, certificate verification enabled, server name
  `loanhub.co.ls` and configured trust roots.
- Exactly one client certificate with a private key is configured.
- Keep-alive is disabled, timeouts are bounded and redirect handling is
  explicitly configured.

The factory tests now use the hardened constructor with test certificate
material, not a generic `http.Client`. Negative tests reject missing
client certs, a missing CA, insecure verification, TLS 1.2 minimum,
unexpected hosts, non-mTLS transports and unbounded timeouts.

**Security boundary:** These are construction-time checks, not proof
that a live TLS server validated the client certificate or that a
particular endpoint completed an authenticated handshake. A live,
trusted TLS-terminating ASGI server must still be integrated and tested.
The SDK WebSocket remains unmounted, and the normal diagnostics service
and contract-signing routes are unchanged.
