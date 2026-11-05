"""Real TLS 1.3 client-certificate handshake contract for Wacom transport."""
from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.wacom_tls_peer_adapter import verified_wacom_tls_scope
from core.wacom_mtls_identity import _verified_workstation_from_tls


def _make_tls_material(tmp_path):
    now = datetime.now(timezone.utc)
    root_key = ed25519.Ed25519PrivateKey.generate()
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Wacom test CA")])
    root = (
        x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name)
        .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(root_key, algorithm=None)
    )
    ca = root.public_bytes(serialization.Encoding.PEM)
    (tmp_path / "ca.pem").write_bytes(ca)

    def leaf(name, usage):
        key = ed25519.Ed25519PrivateKey.generate()
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
        certificate = (
            x509.CertificateBuilder().subject_name(subject).issuer_name(root_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=5))
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
            .sign(root_key, algorithm=None)
        )
        (tmp_path / f"{name}.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (tmp_path / f"{name}.key").write_bytes(
            key.private_bytes(serialization.Encoding.PEM,
                              serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
        )
        return certificate.public_bytes(serialization.Encoding.DER)

    leaf("server", ExtendedKeyUsageOID.SERVER_AUTH)
    client_der = leaf("wacom-client", ExtendedKeyUsageOID.CLIENT_AUTH)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.verify_mode = ssl.CERT_REQUIRED
    server_ctx.load_verify_locations(cafile=str(tmp_path / "ca.pem"))
    server_ctx.load_cert_chain(str(tmp_path / "server.pem"), str(tmp_path / "server.key"))
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.check_hostname = False
    client_ctx.verify_mode = ssl.CERT_REQUIRED
    client_ctx.load_verify_locations(cafile=str(tmp_path / "ca.pem"))
    client_ctx.load_cert_chain(str(tmp_path / "wacom-client.pem"), str(tmp_path / "wacom-client.key"))
    return server_ctx, client_ctx, client_der


def _complete_handshake(server_ctx, client_ctx):
    server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    server = server_ctx.wrap_bio(server_in, server_out, server_side=True)
    client = client_ctx.wrap_bio(client_in, client_out, server_side=False, server_hostname="localhost")
    server_done, client_done = False, False
    for _ in range(40):
        if not client_done:
            try:
                client.do_handshake()
                client_done = True
            except ssl.SSLWantReadError:
                pass
        chunk = client_out.read()
        if chunk:
            server_in.write(chunk)
        if not server_done:
            try:
                server.do_handshake()
                server_done = True
            except ssl.SSLWantReadError:
                pass
        chunk = server_out.read()
        if chunk:
            client_in.write(chunk)
        if client_done and server_done:
            return server
    raise AssertionError("TLS handshake did not complete")


def test_real_mutually_verified_tls_peer_works_with_identity_pin(tmp_path, monkeypatch):
    import hashlib
    import json

    server_ctx, client_ctx, leaf = _make_tls_material(tmp_path)
    peer = _complete_handshake(server_ctx, client_ctx)
    scope = {
        "type": "http", "path": "/api/v1/wacom/connector/preview-introspect",
        "extensions": {"tls": {"client_cert_verified": False}},
        "verified_wacom_client_workstation_id": "untrusted",
    }
    bridged = verified_wacom_tls_scope(scope, ssl_peer=peer, server_context=server_ctx)
    assert bridged["extensions"]["tls"]["client_cert_verified"] is True
    assert bridged["extensions"]["tls"]["client_cert_chain"] == (leaf,)
    assert "verified_wacom_client_workstation_id" not in bridged
    assert scope["extensions"]["tls"]["client_cert_verified"] is False

    workstation = str(uuid4())
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_WACOM_MTLS_CERT_PINS_JSON",
                       json.dumps({workstation: hashlib.sha256(leaf).hexdigest()}))
    assert str(_verified_workstation_from_tls(bridged)) == workstation


def test_unverified_transport_cannot_mint_identity(tmp_path):
    server_ctx, client_ctx, _ = _make_tls_material(tmp_path)
    server_ctx.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match="mandatory"):
        verified_wacom_tls_scope({"type": "http"}, ssl_peer=object(), server_context=server_ctx)
    server_ctx.verify_mode = ssl.CERT_REQUIRED
    with pytest.raises(ValueError, match="real TLS"):
        verified_wacom_tls_scope({"type": "http"}, ssl_peer=object(), server_context=server_ctx)
    with pytest.raises(ValueError, match="HTTP"):
        verified_wacom_tls_scope({"type": "websocket"}, ssl_peer=object(), server_context=server_ctx)
