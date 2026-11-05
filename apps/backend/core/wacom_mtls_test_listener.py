"""Standalone mTLS-only ASGI gateway for supervised Wacom backend testing.

DO NOT put this behind an HTTP proxy: only a direct TLS socket whose
server-side handshake required a verified client certificate is trusted.
This tiny HTTP/1.1 adapter intentionally supports one bounded JSON POST per
connection; no pipelining, transfer encoding, forwarding, or generic APIs.
It does not replace the normal LoanHub application server.
"""
from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Awaitable, Callable
from typing import Any

from core.wacom_tls_peer_adapter import verified_wacom_tls_scope

_WACOM_PATH = "/api/v1/wacom/connector/preview-introspect"
_MAX_BODY = 4096
_MAX_HEADERS = 8192
_MAX_RESPONSE = 16384
_RESPONSE_NAMES = {200: b"OK", 400: b"Bad Request", 403: b"Forbidden",
                   404: b"Not Found", 405: b"Method Not Allowed",
                   413: b"Payload Too Large", 500: b"Internal Server Error"}


def make_verified_wacom_server_context(
    *, certfile: str, keyfile: str, client_ca_file: str
) -> ssl.SSLContext:
    if not all((certfile, keyfile, client_ca_file)):
        raise ValueError("Wacom TLS certificates and trusted client CA required")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=client_ca_file)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def _request_scope(raw_head: bytes) -> tuple[dict[str, Any], int]:
    if len(raw_head) > _MAX_HEADERS or not raw_head.endswith(b"\r\n\r\n"):
        raise ValueError("malformed header boundary")
    lines = raw_head[:-4].split(b"\r\n")
    if lines[0] != b"POST " + _WACOM_PATH.encode("ascii") + b" HTTP/1.1":
        raise ValueError("unexpected HTTP route")
    headers = []
    count = 0
    length = None
    host = None
    for line in lines[1:]:
        if b":" not in line or line[:1] in (b" ", b"\t"):
            raise ValueError("invalid HTTP header")
        name, value = line.split(b":", 1)
        name = name.lower()
        value = value.strip(b" \t")
        if not name or not all(33 <= char <= 126 for char in name + value):
            raise ValueError("invalid header characters")
        if name in (b"transfer-encoding", b"upgrade", b"proxy-authorization",
                    b"connection", b"expect", b"cookie", b"authorization"):
            raise ValueError("unsupported HTTP mechanism")
        if name == b"content-length":
            if length is not None or not value.isdigit():
                raise ValueError("invalid HTTP length")
            length = int(value)
        if name == b"host":
            count += 1
            host = value
        headers.append((name, value))
    if count != 1 or host != b"loanhub.co.ls" or length is None or not 0 < length <= _MAX_BODY:
        raise ValueError("invalid request length or host")
    if sum(1 for name, _ in headers if name == b"content-type") != 1:
        raise ValueError("content-type required")
    if not any(name == b"content-type" and value == b"application/json" for name, value in headers):
        raise ValueError("only JSON supported")
    return {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "POST", "scheme": "https",
        "path": _WACOM_PATH, "raw_path": _WACOM_PATH.encode(),
        "query_string": b"", "root_path": "", "headers": headers,
        "server": ("loanhub.co.ls", 443), "client": None,
    }, length


async def handle_verified_wacom_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    *, app: Callable[..., Awaitable[Any]], context: ssl.SSLContext,
) -> None:
    """Serve exactly one strict ASGI request over a verified server TLS peer."""
    status = 403
    response = b""
    try:
        peer = writer.get_extra_info("ssl_object")
        if peer is None:
            raise ValueError("no direct TLS peer")
        # Do not parse a single user-supplied HTTP field until peer TLS is
        # confirmed. The transport creates and controls the SSLObject.
        if context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("untrusted TLS policy")
        if peer.version() != "TLSv1.3" or not peer.getpeercert(binary_form=True):
            raise ValueError("TLS client certificate missing")
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=3)
        scope, length = _request_scope(head)
        body = await asyncio.wait_for(reader.readexactly(length), timeout=3)
        scope = verified_wacom_tls_scope(scope, ssl_peer=peer, server_context=context)
        messages = []
        called = False

        async def receive():
            nonlocal called
            if called:
                return {"type": "http.disconnect"}
            called = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)
            if len(messages) > 8:
                raise ValueError("too many ASGI response events")

        await asyncio.wait_for(app(scope, receive, send), timeout=5)
        starts = [msg for msg in messages if msg.get("type") == "http.response.start"]
        chunks = [msg for msg in messages if msg.get("type") == "http.response.body"]
        if len(starts) != 1 or not chunks or chunks[-1].get("more_body"):
            raise ValueError("invalid ASGI response")
        status = starts[0]["status"]
        if type(status) is not int or not 200 <= status <= 599:
            raise ValueError("invalid status code")
        response = b"".join(msg.get("body", b"") for msg in chunks)
        if len(response) > _MAX_RESPONSE:
            raise ValueError("oversized ASGI response")
    except (ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError,
            asyncio.LimitOverrunError):
        status, response = 403, b""
    except Exception:
        status, response = 500, b""
    try:
        reason = _RESPONSE_NAMES.get(status, b"Result")
        writer.write(
            b"HTTP/1.1 " + str(status).encode() + b" " + reason + b"\r\n"
            b"Content-Type: application/json\r\nCache-Control: no-store\r\n"
            b"Connection: close\r\nContent-Length: " + str(len(response)).encode()
            + b"\r\n\r\n" + response
        )
        await asyncio.wait_for(writer.drain(), timeout=2)
    except (OSError, ConnectionError, asyncio.TimeoutError):
        pass
    finally:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=2)
        except (OSError, ConnectionError, asyncio.TimeoutError):
            pass


async def start_verified_wacom_listener(
    *, app, server_context: ssl.SSLContext, host: str = "127.0.0.1",
    port: int = 0,
) -> asyncio.AbstractServer:
    # Loopback-only by default, and no wildcard or LAN bind supported by
    # this test fixture. Operator-controlled TCP routing must separately be
    # security-reviewed rather than inferred from HTTP proxy headers.
    if host != "127.0.0.1" or server_context.verify_mode != ssl.CERT_REQUIRED:
        raise ValueError("Wacom test listener must use loopback and verified mTLS")
    if server_context.minimum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("Wacom test listener requires TLS1.3")
    return await asyncio.start_server(
        lambda reader, writer: handle_verified_wacom_connection(
            reader, writer, app=app, context=server_context
        ),
        host=host, port=port, ssl=server_context, limit=_MAX_HEADERS,
    )
