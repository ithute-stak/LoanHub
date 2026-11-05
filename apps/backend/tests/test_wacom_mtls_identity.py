"""Tests for Wacom connector client-certificate identity mapping."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.wacom_mtls_identity import (
    WacomVerifiedMTLSIdentityMiddleware,
    _verified_workstation_from_tls,
)


def _certificate():
    key = ed25519.Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-wacom")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-wacom")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(minutes=5))
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(key, algorithm=None)
    )
    return cert.public_bytes(serialization.Encoding.DER)


def _tls_scope(cert, verified=True):
    return {"type": "http", "method": "POST",
            "path": "/api/v1/wacom/connector/preview-introspect",
            "headers": [], "extensions": {"tls": {
                "client_cert_verified": verified,
                "client_cert_chain": [cert],
            }}}


def test_identity_requires_verified_tls_certificate_and_pin(monkeypatch):
    cert = _certificate()
    workstation = uuid4()
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv(
        "LOANHUB_WACOM_MTLS_CERT_PINS_JSON",
        json.dumps({str(workstation): hashlib.sha256(cert).hexdigest()}),
    )
    assert _verified_workstation_from_tls(_tls_scope(cert)) == workstation
    assert _verified_workstation_from_tls(_tls_scope(cert, False)) is None
    assert _verified_workstation_from_tls({"type": "http", "headers": [
        (b"x-ssl-client-verify", b"SUCCESS"),
        (b"x-workstation-id", str(workstation).encode()),
    ]}) is None
    monkeypatch.setenv("LOANHUB_WACOM_MTLS_CERT_PINS_JSON", "{}")
    assert _verified_workstation_from_tls(_tls_scope(cert)) is None
    monkeypatch.setenv("LOANHUB_WACOM_MTLS_CERT_PINS_JSON", "{invalid")
    assert _verified_workstation_from_tls(_tls_scope(cert)) is None
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "false")
    assert _verified_workstation_from_tls(_tls_scope(cert)) is None


def test_middleware_scrubs_forged_scope_identity(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", raising=False)
    workstation = uuid4()
    seen = []

    async def downstream(scope, receive, send):
        seen.append(scope)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    incoming = _tls_scope(_certificate())
    incoming["verified_wacom_client_workstation_id"] = workstation
    asyncio.run(WacomVerifiedMTLSIdentityMiddleware(downstream)(incoming, receive, send))
    assert "verified_wacom_client_workstation_id" not in seen[0]
    assert incoming["verified_wacom_client_workstation_id"] == workstation
