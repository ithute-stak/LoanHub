"""Contracts for PostgreSQL least-privilege runtime access."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_role_is_distinct_and_non_privileged() -> None:
    script = _read("scripts/ensure_database_runtime_role.sh")

    assert 'DB_RUNTIME_USER must be different from the database owner DB_USER' in script
    assert "NOSUPERUSER" in script
    assert "NOCREATEDB" in script
    assert "NOCREATEROLE" in script
    assert "NOREPLICATION" in script
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in script
    assert "GRANT USAGE ON SCHEMA public" in script
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public" in script
    assert "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public" in script
    assert "ALTER DEFAULT PRIVILEGES" in script


def test_compose_uses_owner_for_migrations_and_runtime_for_app_services() -> None:
    compose = _read("compose.yaml")

    bootstrap = compose[compose.index("  db-role-bootstrap:"):compose.index("  migrate:")]
    migrate = compose[compose.index("  migrate:"):compose.index("  backend:")]
    backend = compose[compose.index("  backend:"):compose.index("  maintenance:")]
    maintenance = compose[compose.index("  maintenance:"):compose.index("  rust-compute:")]

    assert 'DB_USER: ${DB_USER:-loanhub}' in bootstrap
    assert 'DB_RUNTIME_USER: ${DB_RUNTIME_USER:-loanhub_app}' in bootstrap
    assert "db-role-bootstrap:" in migrate
    assert "condition: service_completed_successfully" in migrate
    assert 'DB_USER: ${DB_RUNTIME_USER:-loanhub_app}' in backend
    assert 'DB_PASSWORD: ${DB_RUNTIME_PASSWORD:?Set DB_RUNTIME_PASSWORD in .env.production}' in backend
    assert 'DB_USER: ${DB_RUNTIME_USER:-loanhub_app}' in maintenance
    assert 'DB_PASSWORD: ${DB_RUNTIME_PASSWORD:?Set DB_RUNTIME_PASSWORD in .env.production}' in maintenance


def test_deployment_bootstraps_runtime_role_before_runtime_smoke() -> None:
    deploy = _read("scripts/deploy-production-manual.sh")

    bootstrap_pos = deploy.index('run --rm --no-deps db-role-bootstrap')
    smoke_pos = deploy.index("Running candidate backend import smoke")
    migration_pos = deploy.index("Applying Alembic migrations (fail-closed)")
    assert bootstrap_pos < smoke_pos < migration_pos


def test_env_templates_require_separate_runtime_secret() -> None:
    local_env = _read(".env.example")
    prod_env = _read(".env.production.example")
    ci = _read(".github/workflows/ci.yml")

    for source in (local_env, prod_env):
        assert "DB_RUNTIME_USER=loanhub_app" in source
        assert "DB_RUNTIME_PASSWORD=" in source
    assert "DB_RUNTIME_USER: loanhub_app" in ci
    assert "DB_RUNTIME_PASSWORD: ci-only-runtime-postgres-password" in ci
