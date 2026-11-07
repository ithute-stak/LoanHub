"""Tests for the resolved Compose safety gate (synthetic Compose dictionaries)."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts" / "wacom_resolved_compose_gate.py"
spec = importlib.util.spec_from_file_location("wacom_resolved_compose_gate", path)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def fixture():
    name = "loanhub-wacom-stage-ci"
    return {
        "name": name,
        "services": {
            "db": {
                "environment": {"POSTGRES_DB": "loanhub_wacom_staging"},
                "networks": {"loanhub": None},
            },
            "redis": {"networks": {"loanhub": None}},
            "clamav": {"networks": {"loanhub": None}, "expose": ["3310"]},
            "migrate": {
                "networks": {"loanhub": None},
                "volumes": [{"source": "/test/staging-secrets", "target": "/app/secrets", "read_only": True}],
            },
            "backend": {
                "networks": {"loanhub": None},
                "environment": {
                    "ENVIRONMENT": "staging", "FILE_ENCRYPTION_ENABLED": "true",
                    "MALWARE_SCAN_ENABLED": "true",
                    "MALWARE_SCAN_FAIL_CLOSED": "true",
                    "CLAMAV_HOST": "clamav", "CLAMAV_PORT": "3310",
                    "FILE_STORAGE_PATH": "/app/media/staging/uploads",
                    "LELEFAPAYGATE_ENABLED": "false",
                },
                "ports": [{"host_ip": "127.0.0.1", "target": 8000, "published": "18080"}],
                "volumes": [{"source": "/test/staging-secrets", "target": "/app/secrets", "read_only": True}],
            },
        },
        "volumes": {key: {"name": name + "_" + key}
                    for key in ("postgres_data", "redis_data", "loanhub_files")},
        "networks": {"loanhub": {"name": name + "_loanhub"}},
    }


def test_good_synthetic_resolved_compose_passes():
    assert gate.audit(fixture()) == []


def test_rejects_public_edge_and_host_exposed_scanner():
    conf = fixture()
    conf["services"]["backend"]["networks"]["public_edge"] = None
    conf["networks"]["public_edge"] = {"external": True}
    conf["services"]["clamav"]["ports"] = [
        {"host_ip": "0.0.0.0", "target": 3310, "published": "3310"}
    ]
    bad = gate.audit(conf)
    assert any("public_network" in x for x in bad)
    assert "clamav_must_have_no_published_ports" in bad
    assert any("non_loopback_port" in x for x in bad)


def test_rejects_production_project_volumes_and_database():
    conf = fixture()
    conf["name"] = "loanhub"
    conf["services"]["db"]["environment"]["POSTGRES_DB"] = "loanhub"
    conf["volumes"]["postgres_data"]["name"] = "loanhub_postgres_data"
    bad = gate.audit(conf)
    assert "unexpected_compose_project" in bad
    assert "database_name_not_dedicated" in bad


def test_rejects_non_staging_storage_or_missing_encryption():
    conf = fixture()
    conf["services"]["backend"]["environment"]["FILE_ENCRYPTION_ENABLED"] = "false"
    conf["services"]["backend"]["environment"]["FILE_STORAGE_PATH"] = "/app/media/uploads"
    conf["services"]["backend"]["volumes"][0]["read_only"] = False
    bad = gate.audit(conf)
    assert "file_encryption_enabled_not_enabled" in bad
    assert "storage_path_not_staging" in bad
    assert "backend_staging_secrets_not_readonly" in bad
