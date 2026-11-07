"""Real ClamAV (clamd INSTREAM) Wacom scanner contract tests.

Opt-in: WACOM_REAL_CLAMAV_HOST=127.0.0.1; WACOM_REAL_CLAMAV_PORT=33119.
The daemon is provided by the disposable CI container, not production.
EICAR is a standard harmless anti-malware test signature, never malware.
"""
from __future__ import annotations

import os
import socket

import pytest
from fastapi import HTTPException

from services import file_service
from services import malware_scan_service as scanner
from scripts.wacom_real_api_smoke import synthetic_png

# Standard EICAR test fixture in fragments, to avoid false positives in source scanning.
_EICAR_FRAGMENTS = (
    "X5O!P%@AP[4\\PZX54(P^)7CC)7}$",
    "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
)


@pytest.fixture
def clamd(monkeypatch):
    host = os.getenv("WACOM_REAL_CLAMAV_HOST")
    port = os.getenv("WACOM_REAL_CLAMAV_PORT")
    if host is None and port is None:
        pytest.skip("Real ClamAV endpoint is not configured")
    if host not in {"127.0.0.1", "localhost"} or port != "33119":
        pytest.fail("Only disposable local ClamAV port 33119 is allowed")
    monkeypatch.setattr(scanner.settings, "CLAMAV_HOST", host)
    monkeypatch.setattr(scanner.settings, "CLAMAV_PORT", int(port))
    monkeypatch.setattr(scanner.settings, "CLAMAV_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(scanner.settings, "MALWARE_SCAN_ENABLED", True)
    monkeypatch.setattr(scanner.settings, "MALWARE_SCAN_FAIL_CLOSED", True)
    return host, int(port)


def test_actual_clamav_scans_valid_synthetic_png_clean(clamd):
    assert scanner.scan_upload(synthetic_png()) == "clean"
    assert file_service._scan_content(synthetic_png()) == "clean"


def test_actual_clamav_detects_standard_harmless_eicar_test_pattern(clamd):
    fixture = "".join(_EICAR_FRAGMENTS).encode("ascii")
    assert len(fixture) == 68
    with pytest.raises(scanner.MalwareDetectedError):
        scanner.scan_upload(fixture)
    with pytest.raises(HTTPException) as error:
        file_service._scan_content(fixture)
    assert error.value.status_code == 422


def test_actual_clamav_rejects_incorrect_instream_content(clamd):
    """ClamAV must not interpret arbitrary garbage as a clean scan."""
    with pytest.raises((scanner.MalwareDetectedError, scanner.MalwareScannerUnavailableError)):
        # This payload is a real EICAR signature with a byte appended; ClamAV
        # may respond FOUND or ERROR, but never an accepted clean result.
        scanner._clamav_instream("".join(_EICAR_FRAGMENTS).encode("ascii")) + b"\x00"
