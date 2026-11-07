"""Wacom signature file storage: actual local encrypted bytes, integrity, and scanner gates.

Uses only ephemeral pytest tmp_path and synthetic PNG. No backend deployment,
network access, Postgres, ClamAV process, signatures or production records.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from scripts.wacom_real_api_smoke import synthetic_png
from services import file_service as files
from services.object_storage_service import LocalObjectStorage


class RecordingDB:
    def __init__(self):
        self.records = []
    def add(self, value):
        self.records.append(value)
    def flush(self):
        pass


@pytest.fixture
def isolated_file_storage(tmp_path, monkeypatch):
    storage = LocalObjectStorage(str(tmp_path / "wacom-test-objects"))
    monkeypatch.setattr(files, "get_storage", lambda provider=None: storage)
    monkeypatch.setattr(files.settings, "FILE_ENCRYPTION_ENABLED", True)
    monkeypatch.setattr(files.settings, "FILE_ENCRYPTION_KEY", "UNIT-TEST-ONLY-" + "a" * 48)
    monkeypatch.setattr(files.settings, "MALWARE_SCAN_ENABLED", True)
    monkeypatch.setattr(files.settings, "MALWARE_SCAN_FAIL_CLOSED", True)
    return storage


def store_synthetic_wacom(db, company_id, owner_id):
    return files.store_bytes(
        db,
        content=synthetic_png(),
        original_name="synthetic-test-only.png",
        mime_type="image/png",
        owner_user_id=owner_id,
        company_id=company_id,
        branch_id=None,
        category="wacom_operator_signature_pending",
        visibility="private",
        description="TEST-ONLY fictional Wacom upload",
        linked_entity_type="wacom_operator",
        linked_entity_id=str(owner_id),
        is_confidential=True,
    )


def test_real_local_storage_encrypts_on_disk_and_decrypts_to_exact_png(
    monkeypatch, isolated_file_storage,
):
    monkeypatch.setattr(files, "scan_upload", lambda raw: "clean")
    db = RecordingDB()
    owner_id, company_id = uuid4(), uuid4()
    saved = store_synthetic_wacom(db, company_id, owner_id)
    actual_png = synthetic_png()
    storage_bytes = isolated_file_storage.get(saved.storage_key)
    assert db.records == [saved]
    assert storage_bytes != actual_png
    assert not storage_bytes.startswith(b"\x89PNG")
    assert saved.is_encrypted is True
    assert saved.encryption_nonce is not None
    assert saved.encryption_version == "aesgcm-v1"
    assert saved.scan_status == "clean"
    assert saved.is_confidential is True
    assert saved.visibility == "private"
    assert saved.company_id == company_id
    assert saved.linked_entity_id == str(owner_id)
    assert saved.checksum_sha256 == hashlib.sha256(actual_png).hexdigest()
    assert files.read_file_bytes(saved) == actual_png


def test_mutated_ciphertext_fails_integrity_without_releasing_image(
    monkeypatch, isolated_file_storage,
):
    monkeypatch.setattr(files, "scan_upload", lambda raw: "clean")
    saved = store_synthetic_wacom(RecordingDB(), uuid4(), uuid4())
    cipher = bytearray(isolated_file_storage.get(saved.storage_key))
    cipher[len(cipher) // 2] ^= 0x01
    isolated_file_storage.put(saved.storage_key, bytes(cipher))
    with pytest.raises(HTTPException) as exc:
        files.read_file_bytes(saved)
    assert exc.value.status_code == 500
    assert "integrity" in exc.value.detail.lower()


@pytest.mark.parametrize("scan_result", [
    "scanner_unavailable", "not_enabled", "indeterminate", "validated",
])
def test_storage_marks_nonclean_scan_unreviewable(
    monkeypatch, isolated_file_storage, scan_result,
):
    monkeypatch.setattr(files, "scan_upload", lambda raw: scan_result)
    saved = store_synthetic_wacom(RecordingDB(), uuid4(), uuid4())
    assert saved.scan_status != "clean"
    assert saved.is_encrypted is True


def test_fail_closed_scanner_error_prevents_file_creation(
    monkeypatch, isolated_file_storage,
):
    from services.malware_scan_service import MalwareScannerUnavailableError
    def unavailable(_raw):
        raise MalwareScannerUnavailableError("TEST scanner unavailable")
    monkeypatch.setattr(files, "scan_upload", unavailable)
    db=RecordingDB()
    with pytest.raises(HTTPException) as exc:
        store_synthetic_wacom(db, uuid4(), uuid4())
    assert exc.value.status_code == 503
    assert db.records == []
    assert list(isolated_file_storage.root.rglob("*.bin")) == []


def test_upload_api_rejects_disabled_malware_scan_before_storage(monkeypatch):
    from routers import local_signatures as api
    from fastapi import Response
    import base64
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(api.settings, "FILE_ENCRYPTION_ENABLED", True)
    monkeypatch.setattr(api.settings, "MALWARE_SCAN_ENABLED", False)
    monkeypatch.setattr(api.settings, "MALWARE_SCAN_FAIL_CLOSED", True)
    ctx = SimpleNamespace(
        company_id=uuid4(), branch_id=None,
        staff=SimpleNamespace(role=next(iter(api.LENDING_ROLES))),
        user=SimpleNamespace(id=uuid4()),
    )
    raw=synthetic_png()
    payload=api.CaptureSubmission(
        signer_kind="operator",
        consent_reference="TEST-ONLY-001",
        capture_png_base64=base64.b64encode(raw).decode("ascii"),
        capture_sha256=hashlib.sha256(raw).hexdigest(),
    )
    db=RecordingDB()
    with pytest.raises(HTTPException) as exc:
        api.upload_capture(payload, Response(), db=db, context=ctx)
    assert exc.value.status_code == 503
    assert db.records == []
