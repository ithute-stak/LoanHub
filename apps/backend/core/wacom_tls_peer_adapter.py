"""Server-side bridge from a real TLS connection to Wacom's ASGI identity.

This is a transport-server integration primitive, NOT HTTP middleware.
Only the TLS-terminating server, which possesses the actual SSL socket or
SSLObject, may call it. Neither request headers nor request-body values
can establish a client certificate.
"""
from __future__ import annotations

import ssl
from typing import Any


def verified_wacom_tls_scope(
    scope: dict[str, Any], *, ssl_peer: ssl.SSLSocket | ssl.SSLObject,
    server_context: ssl.SSLContext,
) -> dict[str, Any]:
    """Return a fresh ASGI scope with verified peer TLS metadata.

    Must be invoked by a directly TLS-terminating ASGI server after a real
    handshake, never from an endpoint or proxy supplied header.
    """
    if scope.get("type") != "http":
        raise ValueError("Wacom TLS bridge accepts HTTP scopes only")
    if server_context.verify_mode != ssl.CERT_REQUIRED:
        raise ValueError("mTLS requires mandatory verified client certificates")
    if not isinstance(ssl_peer, (ssl.SSLSocket, ssl.SSLObject)):
        raise ValueError("Wacom peer must be a real TLS connection")
    # A successful getpeercert call with verify_mode CERT_REQUIRED on the
    # actual server connection yields the validated peer leaf. The server
    # must still establish that this peer uses server_context, not a
    # different or unverified SSLContext. The SSL Python API cannot
    # independently prove the socket was created with this exact context.
    if ssl_peer.version() != "TLSv1.3":
        raise ValueError("Wacom client mTLS requires TLS 1.3")
    leaf = ssl_peer.getpeercert(binary_form=True)
    if not isinstance(leaf, bytes) or not 0 < len(leaf) <= 8192:
        raise ValueError("Wacom verified client certificate unavailable")
    extensions = dict(scope.get("extensions") or {})
    # Never preserve upstream-supplied tls metadata.
    extensions["tls"] = {
        "client_cert_verified": True,
        "client_cert_chain": (leaf,),
    }
    result = dict(scope)
    result["extensions"] = extensions
    result.pop("verified_wacom_client_workstation_id", None)
    return result
