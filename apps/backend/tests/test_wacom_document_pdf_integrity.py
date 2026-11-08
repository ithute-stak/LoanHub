"""Document-bound Wacom consent requires actual decrypted PDF bytes."""
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import wacom_document_intents as routes


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def _source(payload=PDF):
    return SimpleNamespace(size_bytes=len(payload), checksum_sha256=hashlib.sha256(payload).hexdigest())


def test_preparation_checks_the_actual_pdf_bytes(monkeypatch):
    source = _source()
    monkeypatch.setattr(routes, "read_file_bytes", lambda _: PDF)
    routes._verified_source_pdf(source, expected_sha256=source.checksum_sha256)


@pytest.mark.parametrize("tampered", [
    b"%PDF-1.4\nmodified",
    b"NOT A PDF",
    PDF + b"hidden alteration",
])
def test_changed_document_bytes_fail_closed(monkeypatch, tampered):
    source = _source()
    monkeypatch.setattr(routes, "read_file_bytes", lambda _: tampered)
    with pytest.raises(HTTPException) as exc:
        routes._verified_source_pdf(source, expected_sha256=source.checksum_sha256)
    assert exc.value.status_code == 409


def test_oversized_pdf_is_denied_without_reading_storage(monkeypatch):
    source = _source()
    source.size_bytes = 20 * 1024 * 1024 + 1
    monkeypatch.setattr(routes, "read_file_bytes",
                        lambda _: pytest.fail("Oversized file was read from storage"))
    with pytest.raises(HTTPException) as exc:
        routes._verified_source_pdf(source, expected_sha256=source.checksum_sha256)
    assert exc.value.status_code == 413


def test_checksum_metadata_does_not_override_actual_bytes(monkeypatch):
    source = _source()
    monkeypatch.setattr(routes, "read_file_bytes", lambda _: b"same length".ljust(len(PDF), b"x"))
    with pytest.raises(HTTPException):
        routes._verified_source_pdf(source, expected_sha256=source.checksum_sha256)
