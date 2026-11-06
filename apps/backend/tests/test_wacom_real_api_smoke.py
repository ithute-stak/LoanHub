"""Synthetic-only tests for real-API Wacom smoke runner.

These tests never connect to a LoanHub server and never upload signatures.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import struct
from pathlib import Path
from unittest.mock import patch
import zlib

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wacom_real_api_smoke.py"
SPEC = importlib.util.spec_from_file_location("wacom_real_api_smoke", MODULE_PATH)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_requires_explicit_test_host(monkeypatch):
    monkeypatch.delenv("WACOM_TEST_ALLOWED_HOST", raising=False)
    with pytest.raises(ValueError):
        smoke.must_be_test_origin("https://wacom-test.example")
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "wacom-test.example")
    assert smoke.must_be_test_origin("https://wacom-test.example") == "https://wacom-test.example"
    for unsafe in [
        "http://wacom-test.example", "https://user:secret@wacom-test.example",
        "https://wacom-test.example/api", "https://evil.example",
        "https://wacom-test.example/?debug=1",
    ]:
        with pytest.raises(ValueError):
            smoke.must_be_test_origin(unsafe)


def test_real_public_origin_is_rejected_even_if_allowlisted(monkeypatch):
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "loanhub.co.ls")
    with pytest.raises(ValueError):
        smoke.must_be_test_origin("https://loanhub.co.ls")


def test_png_is_synthetic_and_decodable_without_external_libraries():
    png = smoke.synthetic_png()
    assert png.startswith(bytes.fromhex("89504e470d0a1a0a"))
    assert len(png) < 128_000
    ihdr_len = struct.unpack(">I", png[8:12])[0]
    assert ihdr_len == 13
    assert png[12:16] == b"IHDR"
    assert struct.unpack(">II", png[16:24]) == (16, 8)
    assert b"IDAT" in png
    assert png[-8:-4] == b"IEND"
    assert len(hashlib.sha256(png).hexdigest()) == 64


def test_request_refuses_redirects_and_never_returns_backend_error_body(monkeypatch):
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "wacom-test.example")
    api = smoke.LoanHubAPI("https://wacom-test.example")
    import urllib.error
    error = urllib.error.HTTPError(
        "https://wacom-test.example/path", 302, "Found",
        {"Location": "https://evil.example"}, io.BytesIO(b'{"password":"secret"}'),
    )
    class Opener:
        def open(self, *args, **kwargs):
            raise error
    api._opener = Opener()
    status, result = api.request("GET", "/api/v1/local-signatures/me/status")
    assert status == 302
    assert result is None


def test_request_requires_auth_for_tenant_endpoint(monkeypatch):
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "wacom-test.example")
    api = smoke.LoanHubAPI("https://wacom-test.example")
    with pytest.raises(RuntimeError):
        api.request("GET", "/api/v1/local-signatures/me/status", authorized=True)
