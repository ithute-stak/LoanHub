# Wacom trusted TLS peer bridge — tested transport primitive

The Wacom-only backend identity middleware deliberately refuses certificate
fingerprints received through ordinary HTTP headers. A backend API cannot
legitimately infer client-certificate verification from the client's POST body.

The dedicated `core.wacom_tls_peer_adapter.verified_wacom_tls_scope`
helper now gives a **directly TLS-terminating ASGI server** a strict way
to attach TLS connection metadata to the request scope:

- The TLS peer must be a real Python `ssl.SSLSocket` or `ssl.SSLObject`.
- The server-side SSL context must enforce `ssl.CERT_REQUIRED`.
- The completed peer handshake must negotiate TLS 1.3.
- The peer must supply a validated DER client certificate.
- Any existing `extensions.tls` or injected workstation-identity field is
  overwritten, never trusted or forwarded.
- The existing backend middleware separately requires a provisioned
  fingerprint pin, certificate time validity and client-auth EKU, and
  finally revalidates tenant, enrollment, and the live contract/session.

A new integration test creates a temporary test CA plus distinct server
and client certificates, performs a **real mutual TLS 1.3 handshake** with
`ssl.MemoryBIO`, extracts the validated server-side leaf, and verifies
that it maps to the correct pinned workstation. Negative tests cover
missing mandatory TLS verification, fake SSL peers and wrong scope type.

## Deployment remains blocked

This helper is **not yet wired into Uvicorn**, Hypercorn, an edge proxy or
the production Docker composition. Python's `ssl` API does not itself
prove that a provided SSL peer was created from the supplied context:
the **TLS-terminating server must control both objects** and call this
helper only after its own successfully verified handshake, before
dispatching the ASGI request.

Standard reverse proxies do not automatically expose TLS socket objects
to backend Uvicorn. Do not synthesize `client_cert_verified=True` from
`X-SSL-Client-Cert`, `X-Forwarded-Client-Cert`, or even proxy-local
headers. A trusted in-process TLS server adapter, or an independently
security-reviewed transport boundary with equivalent authenticated
metadata, must still be implemented and deployed. No physical SDK
capture or binding contract signing is enabled by this code.
