from __future__ import annotations

import inspect
from pathlib import Path

import bleach

from database.models.notification import Notification
from services.workspace_document_service import sanitize_document_html


def test_document_sanitizer_supports_installed_bleach_runtime() -> None:
    source = '''
        <h1 style="color: #123456; text-align: center">Loan agreement</h1>
        <p onclick="alert(1)">Safe text<script>alert(2)</script></p>
    '''

    result = sanitize_document_html(source)

    assert "Loan agreement" in result
    assert "Safe text" in result
    assert "onclick" not in result
    assert "<script" not in result


def test_bleach_compatibility_path_matches_runtime_signature() -> None:
    parameters = inspect.signature(bleach.clean).parameters

    # The service must work with either the modern CSSSanitizer API, the
    # legacy styles API, or its safe no-inline-style fallback.
    assert "text" in parameters
    assert sanitize_document_html("<p style='font-weight:bold'>Test</p>")


def test_notification_action_label_is_stored_in_json_data() -> None:
    notification = Notification(
        user_id="00000000-0000-0000-0000-000000000001",
        title="System error detected",
        message="A request failed.",
        data={"action_label": "Investigate error"},
    )

    assert notification.data["action_label"] == "Investigate error"


def test_notification_call_sites_do_not_use_unknown_action_label_column() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    monitored_files = (
        backend_root / "core" / "error_monitoring.py",
        backend_root / "routers" / "auth.py",
    )

    for path in monitored_files:
        source = path.read_text(encoding="utf-8")
        assert "action_label=" not in source
