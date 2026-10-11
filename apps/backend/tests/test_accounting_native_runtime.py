from decimal import Decimal

import pytest

from services import accounting_native_runtime as native


def test_missing_library_falls_back(monkeypatch):
    monkeypatch.delenv("LOANHUB_CPP_LIBRARY_PATH", raising=False)
    rows = [(101, Decimal("1.00"), Decimal("0.00")), (201, Decimal("0.00"), Decimal("1.00"))]
    result = native.advisory_trial_balance(rows)
    assert result["native_cpp_matched"] is False
    assert result["authoritative"] is False


def test_rejects_unsupported_native_command():
    with pytest.raises(ValueError):
        native.native_accounting_execute("post-journal", "101|100|0")


def test_missing_native_path_returns_none(monkeypatch):
    monkeypatch.setenv("LOANHUB_CPP_LIBRARY_PATH", "/nonexistent/loanhub-native.so")
    assert native.native_accounting_execute("accounting-trial-balance", "101|100|0\n") is None


def test_parity_when_real_library_available(monkeypatch):
    path = __import__("os").environ.get("LOANHUB_CPP_LIBRARY_PATH")
    if not path:
        pytest.skip("native library not configured for this test run")
    rows = [(101, Decimal("1.00"), Decimal("0.00")), (201, Decimal("0.00"), Decimal("1.00"))]
    result = native.advisory_trial_balance(rows)
    assert result["native_cpp_matched"] is True
    assert result["authoritative"] is False
