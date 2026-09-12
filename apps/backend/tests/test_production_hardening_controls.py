from __future__ import annotations

from pathlib import Path

import pytest

from core.security_middleware import parse_rate_rule
from services.object_storage_service import LocalObjectStorage


def test_rate_limit_parser_supports_operational_rules():
    assert parse_rate_rule('10/minute').limit == 10
    assert parse_rate_rule('100/hour').window_seconds == 3600
    with pytest.raises(ValueError):
        parse_rate_rule('0/minute')
    with pytest.raises(ValueError):
        parse_rate_rule('broken')


def test_local_object_storage_blocks_traversal_and_round_trips(tmp_path: Path):
    storage = LocalObjectStorage(str(tmp_path))
    storage.put('tenant/document.bin', b'encrypted-payload')
    assert storage.get('tenant/document.bin') == b'encrypted-payload'
    with pytest.raises(ValueError):
        storage.put('../escape.bin', b'bad')
    storage.delete('tenant/document.bin')
    with pytest.raises(FileNotFoundError):
        storage.get('tenant/document.bin')


def test_backend_runtime_exposes_application_root_on_pythonpath():
    backend_root = Path(__file__).resolve().parents[1]
    dockerfile = (backend_root / 'Dockerfile').read_text()
    assert 'PYTHONPATH=/app' in dockerfile


def test_production_env_generates_first_superadmin_credential():
    repository_root = Path(__file__).resolve().parents[3]
    template = (repository_root / '.env.production.example').read_text()
    helper = (repository_root / 'scripts' / 'prepare_production_env.sh').read_text()

    assert 'BOOTSTRAP_SUPERADMIN_ENABLED=true' in template
    assert 'BOOTSTRAP_SUPERADMIN_PASSWORD=replace-with-long-random-bootstrap-password' in template
    assert 'set_env BOOTSTRAP_SUPERADMIN_PASSWORD "$BOOTSTRAP_PASSWORD"' in helper
    assert 'secrets/initial_superadmin_password.txt' in helper


def test_frontend_production_image_keeps_runtime_dependencies_and_boots_during_build():
    repository_root = Path(__file__).resolve().parents[3]
    dockerfile = (repository_root / 'apps' / 'frontend' / 'Dockerfile').read_text()

    assert 'FROM dependencies AS production-dependencies' in dockerfile
    assert 'pnpm prune --prod' in dockerfile
    assert '/app/node_modules ./node_modules' in dockerfile
    assert 'node server.js >/tmp/loanhub-frontend-smoke.log' in dockerfile
    assert 'wget -qO- http://127.0.0.1:3000/' in dockerfile
