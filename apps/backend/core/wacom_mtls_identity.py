"""Fail-closed mTLS workstation identity bridge for the connector-only route.

No HTTP header establishes workstation identity. A trusted ASGI TLS terminator
must supply a verified TLS extension on the actual connection; without one,
the connector endpoint remains inaccessible. Disabled by default.

Deployment must pin each enrolled workstation certificate fingerprint to its
workstation UUID. Never forward caller-controlled TLS-extension metadata.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import UUID

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID


_INTROSPECTION_PATH = "/api/v1/wacom/connector/preview-introspect"


def _verified_workstation_from_tls(scope: dict) -> UUID | None:
    if os.getenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED") != "true":
        return None
    # Only a trusted TLS ASGI server may populate this extension. The
    # boolean is an explicit transport integration contract, NOT a public
    # header or value parsed from the client certificate's contents.
    tls = (scope.get("extensions") or {}).get("tls")
    if not isinstance(tls, dict) or tls.get("client_cert_verified") is not True:
        return None
    chain = tls.get("client_cert_chain")
    if not isinstance(chain, (tuple, list)) or not chain or len(chain) > 4:
        return None
    cert_der = chain[0]
    if not isinstance(cert_der, bytes) or not 0 < len(cert_der) <= 8192:
        return None
    try:
        cert = x509.load_der_x509_certificate(cert_der)
        now = datetime.now(timezone.utc)
        if not (cert.not_valid_before_utc <= now < cert.not_valid_after_utc):
            return None
        if ExtendedKeyUsageOID.CLIENT_AUTH not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
            return None
        # Provisioned only by the operator in protected deployment secrets.
        # The exact certificate fingerprint is independent of token claims.
        pin_json = os.getenv("LOANHUB_WACOM_MTLS_CERT_PINS_JSON", "")
        if not pin_json or len(pin_json) > 8192:
            return None
        pins = json.loads(pin_json)
        if not isinstance(pins, dict) or not 0 < len(pins) <= 64:
            return None
        digest = hashlib.sha256(cert_der).hexdigest()
        matches = []
        for workstation, allowed_digest in pins.items():
            workstation_uuid = UUID(workstation)
            if str(workstation_uuid) != workstation:
                return None
            if not isinstance(allowed_digest, str) or len(allowed_digest) != 64:
                return None
            if not all(c in "0123456789abcdef" for c in allowed_digest):
                return None
            if hashlib.sha256(cert_der).hexdigest() == allowed_digest:
                matches.append(workstation_uuid)
        if len(matches) != 1 or digest not in pins.values():
            return None
        return matches[0]
    except (ValueError, TypeError, KeyError, x509.ExtensionNotFound, json.JSONDecodeError):
        return None


class WacomVerifiedMTLSIdentityMiddleware:
    """Set trusted identity only for server-verified, pinned client TLS."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Always overwrite any upstream-injected identity marker.
        downstream_scope = dict(scope)
        downstream_scope.pop("verified_wacom_client_workstation_id", None)
        if scope.get("path") == _INTROSPECTION_PATH:
            verified = _verified_workstation_from_tls(scope)
            if verified is not None:
                downstream_scope["verified_wacom_client_workstation_id"] = verified
        await self.app(downstream_scope, receive, send)
