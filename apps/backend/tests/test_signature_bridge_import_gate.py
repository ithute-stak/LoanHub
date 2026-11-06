"""Security regression: importing signatures is disabled unless explicitly staged."""
import pytest
from fastapi import HTTPException
from routers import signature_bridge

def test_import_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(HTTPException) as exc:
        signature_bridge._enabled()
    assert exc.value.status_code == 503

def test_import_rejected_in_production_even_if_flag_set(monkeypatch):
    monkeypatch.setenv("LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc:
        signature_bridge._enabled()
    assert exc.value.status_code == 503

def test_missing_encryption_key_fails_closed(monkeypatch):
    monkeypatch.delenv("LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        signature_bridge._fernet()
    assert exc.value.status_code == 503
