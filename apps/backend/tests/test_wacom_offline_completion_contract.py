"""Offline regression guards for serialized, consent-bound Wacom uploads.

These are source-contract checks. Real PostgreSQL concurrency must be tested
separately before production approval.
"""
import ast
import inspect

from routers import local_signatures


def test_pending_capture_lookup_filters_unsafe_files():
    source = inspect.getsource(local_signatures._pending_file)
    for expected in (
        "ManagedFile.is_deleted.is_(False)",
        "ManagedFile.is_confidential.is_(True)",
        'ManagedFile.visibility == "private"',
        "ManagedFile.is_encrypted.is_(True)",
        'ManagedFile.scan_status == "clean"',
    ):
        assert expected in source


def test_upload_serializes_retries_before_reading_pending_evidence():
    source = inspect.getsource(local_signatures.upload_capture)
    assert "pg_advisory_xact_lock(:key)" in source
    assert source.index("pg_advisory_xact_lock(:key)") < source.index("existing = _pending_file(")
    assert "Capture already pending under another consent reference" in source
    assert "db.rollback()" in source
    assert "db.commit()" in source


def test_upload_receipts_never_authorize_document_signing():
    source = inspect.getsource(local_signatures.upload_capture)
    tree = ast.parse(source)
    returns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            literals = {
                key.value: value.value
                for key, value in zip(node.value.keys, node.value.values)
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)
            }
            returns.append(literals)
    assert returns
    assert all(item.get("usable_for_signing") is False for item in returns)
