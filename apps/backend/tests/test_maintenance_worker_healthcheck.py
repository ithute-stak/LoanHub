"""Maintenance is a scheduled worker, not an HTTP service."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_maintenance_healthcheck_is_not_backend_http_probe():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    section = compose.split("\n  maintenance:\n", 1)[1].split("\n  rust-compute:\n", 1)[0]
    assert 'command: ["python", "docker/maintenance.py"]' in section
    assert "loanhub-maintenance-heartbeat" in section
    assert "healthcheck:" in section
    assert "127.0.0.1:8000" not in section


def test_maintenance_updates_heartbeat_only_after_successful_work():
    source = (ROOT / "apps/backend/docker/maintenance.py").read_text(encoding="utf-8")
    completed = source.index('logger.info("Maintenance completed:')
    heartbeat = source.index('Path("/tmp/loanhub-maintenance-heartbeat").touch()')
    except_block = source.index("except Exception:", completed)
    assert completed < heartbeat < except_block
