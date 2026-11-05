"""On-the-wire mTLS tests for the isolated Wacom ASGI introspection listener."""
from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
from uuid import uuid4

import pytest

from core.wacom_mtls_identity import WacomVerifiedMTLSIdentityMiddleware
from core.wacom_mtls_test_listener import (
    _request_scope,
    handle_verified_wacom_connection,
    start_verified_wacom_listener,
)
from test_wacom_tls_peer_adapter import _make_tls_material

_PATH = "/api/v1/wacom/connector/preview-introspect"


def test_strict_one_request_parser_rejects_smuggling_and_unrelated_paths():
    request = (
        b"POST " + _PATH.encode() + b" HTTP/1.1\r\n"
        b"Host: loanhub.co.ls\r\nContent-Type: application/json\r\n"
        b"Content-Length: 2\r\n\r\n"
    )
    scope, size = _request_scope(request)
    assert size == 2
    assert scope["path"] == _PATH
    for malicious in (
        request.replace(b"Content-Length: 2", b"Content-Length: 2\r\nContent-Length: 2"),
        request.replace(b"Content-Length: 2", b"Transfer-Encoding: chunked"),
        request.replace(b"Host: loanhub.co.ls", b"Host: evil.example"),
        request.replace(b"POST " + _PATH.encode(), b"POST /api/v1/users"),
        request.replace(b"Content-Type: application/json", b"Content-Type: text/plain"),
        request.replace(b"Content-Length: 2", b"Content-Length: 5000"),
        request.replace(b"Content-Length: 2", b"Content-Length: 2\r\nConnection: keep-alive"),
        request.replace(b"Content-Length: 2", b"Content-Length: 2\r\nAuthorization: Bearer untrusted"),
    ):
        with pytest.raises(ValueError):
            _request_scope(malicious)


def test_actual_tcp_tls_client_identity_reaches_asgi_without_headers(tmp_path, monkeypatch):
    server_ctx, client_ctx, leaf = _make_tls_material(tmp_path)
    workstation_id = uuid4()
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_WACOM_MTLS_CERT_PINS_JSON",
                       json.dumps({str(workstation_id): hashlib.sha256(leaf).hexdigest()}))

    observed = []

    async def app(scope, receive, send):
        observed.append(scope.get("verified_wacom_client_workstation_id"))
        message = await receive()
        assert message["body"] == b"{}"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b'{"authenticated":true}'})

    protected = WacomVerifiedMTLSIdentityMiddleware(app)

    async def run():
        listener = await start_verified_wacom_listener(
            app=protected, server_context=server_ctx,
        )
        try:
            port = listener.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", port, ssl=client_ctx, server_hostname="localhost",
            )
            writer.write(
                b"POST " + _PATH.encode() + b" HTTP/1.1\r\n"
                b"Host: loanhub.co.ls\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}"
            )
            await writer.drain()
            head = await asyncio.wait_for(reader.readuntil(b"\\r\\n\\r\\n"), timeout=5)
            assert b"HTTP/1.1 200 OK" in head
            body = await asyncio.wait_for(reader.readexactly(22), timeout=5)
            assert body == b'{"authenticated":true}'
            writer.close()
            await writer.wait_closed()
        finally:
            listener.close()
            await listener.wait_closed()

    asyncio.run(run())
    assert observed == [workstation_id]


def test_listener_refuses_untrusted_bind_or_server_policy(tmp_path):
    server_ctx, _, _ = _make_tls_material(tmp_path)

    async def no_op(scope, receive, send):
        raise AssertionError("must not call ASGI app")

    async def run():
        with pytest.raises(ValueError, match="loopback"):
            await start_verified_wacom_listener(
                app=no_op, server_context=server_ctx, host="0.0.0.0",
            )
        server_ctx.verify_mode = ssl.CERT_NONE
        with pytest.raises(ValueError, match="mTLS"):
            await start_verified_wacom_listener(
                app=no_op, server_context=server_ctx,
            )

    asyncio.run(run())
