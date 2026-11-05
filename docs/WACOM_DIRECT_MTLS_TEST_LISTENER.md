# Wacom dedicated direct-mTLS ASGI test listener

The backend now includes `core/wacom_mtls_test_listener.py`: a
**loopback-only, explicitly invoked test transport** that performs actual
server-side TLS 1.3 client-certificate verification and transports a
single, bounded JSON POST to the existing ASGI application.

This is deliberately **not** loaded by the production FastAPI/Uvicorn
startup and does not expose a new route in the public application.

## What is authenticated

- The server owns the TLS `SSLContext` and negotiates the actual connection
  with `ssl.CERT_REQUIRED` against a locally provisioned client CA.
- Only the TLS server's `StreamWriter.get_extra_info("ssl_object")` is
  allowed as the client-certificate source; forwarded or spoofed HTTP
  certificate headers are never interpreted.
- The existing `verified_wacom_tls_scope` adapter puts that actual
  verified certificate into the per-request ASGI TLS extension.
- `WacomVerifiedMTLSIdentityMiddleware` independently checks the
  configured certificate fingerprint pin and enrolled workstation UUID.
- The existing introspection route additionally verifies the signed
  preview ticket, tenant, operator, contract, workstation and active
  signing-session state.

The test transport supports *only*
`POST /api/v1/wacom/connector/preview-introspect` with a single JSON
Content-Length body of up to 4096 bytes and exact Host
`loanhub.co.ls`. It rejects chunked transfer, duplicate lengths,
keep-alives, cookies, authorization headers, and other API paths. It
closes every connection after a bounded ASGI response.

## Integration test

`tests/test_wacom_mtls_test_listener.py` exercises the live transport
using a temporary CA and separate server/client certificates. It opens
an actual TCP TLS 1.3 connection to a randomly chosen loopback port,
submits an introspection-path request and verifies that the ASGI
middleware receives the UUID pinned to the **actual peer certificate**.
It also checks strict HTTP request parsing and refusal of wildcard
interfaces or non-mTLS server contexts.

## Still not a production TLS gateway

This module is **not a general HTTP server** and must not be deployed as
a replacement for Uvicorn or as an unaudited public 443 listener. It
only binds 127.0.0.1. A normal HTTP reverse proxy terminates TLS before
the app and cannot forward an authenticated TLS socket or its server
verification context. The Go connector currently pins
`https://loanhub.co.ls` on port 443, so this loopback test listener
does not yet satisfy that network topology.

An approved dedicated mTLS ingress path (for example a dedicated
hostname with TCP/TLS passthrough and separately pinned workstation
certificates), deployment identity/certificate provisioning, TLS
termination architecture review and real end-to-end testing are
required before allowing device capture. Do not change the working
production diagnostics service or claim browser handwriting works.
