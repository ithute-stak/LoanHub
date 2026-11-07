"""Guardrails for the opt-in Wacom staging Compose blueprint.

No Docker daemon, disk mutations or deployment required.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "compose.wacom-staging.yml"
BASE = ROOT / "compose.yaml"


def test_wacom_overlay_has_no_public_edge_network():
    text = OVERLAY.read_text()
    assert "public_edge" not in text
    assert "compose.edge.yml" not in text
    assert "  clamav:" in text
    assert 'CLAMAV_NO_FRESHCLAMD: "true"' in text
    assert "127.0.0.1:" in text
    assert "staging-secrets" in text
    assert "/app/media/staging/uploads" in text
    assert "LELEFAPAYGATE_ENABLED" in text


def test_wacom_overlay_forces_encrypted_fail_closed_scanning():
    text = OVERLAY.read_text()
    for key in (
        "FILE_ENCRYPTION_ENABLED",
        "MALWARE_SCAN_ENABLED",
        "MALWARE_SCAN_FAIL_CLOSED",
    ):
        assert text.count(key + ': "true"') >= 2


def test_compose_uses_project_scoped_database_volumes():
    base = BASE.read_text()
    assert "name: ${COMPOSE_PROJECT_NAME:-loanhub}" in base
    assert "- postgres_data:/var/lib/postgresql/data" in base
    assert "- loanhub_files:/app/media" in base
    assert "DB_NAME: ${DB_NAME:-loanhub}" in base


def test_clamav_not_exposed_to_host():
    text = OVERLAY.read_text()
    scanner = text.split("  clamav:", 1)[1].split("  migrate:", 1)[0]
    assert "ports:" not in scanner
    assert '      - "3310"' in scanner
    assert "networks: [loanhub]" in scanner
