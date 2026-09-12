from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_COMPANY_ROLES = {
    "company_owner",
    "company_admin",
    "branch_manager",
    "loan_officer",
    "finance_officer",
    "collections_officer",
    "compliance_officer",
    "auditor",
    "customer_support",
    "hr_manager",
    "performance_manager",
    "risk_manager",
    "it_support",
    "credit_analyst",
    "aml_cft_officer",
    "treasury_officer",
    "data_protection_officer",
    "regulatory_reporting_officer",
    "operations_officer",
    "information_security_officer",
}


def _seed_constants() -> dict[str, object]:
    source = (REPOSITORY_ROOT / "apps" / "backend" / "scripts" / "seed_sandbox.py").read_text()
    tree = ast.parse(source)
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {"SAMPLE_CLIENTS"}:
            constants[target.id] = ast.literal_eval(node.value)
    return constants


def test_sandbox_uses_separate_database_redis_files_and_internal_network():
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text()

    assert "sandbox_db:" in compose
    assert "DB_HOST: sandbox_db" in compose
    assert "DB_NAME: loanhub_sandbox" in compose
    assert "sandbox_postgres_data:/var/lib/postgresql/data" in compose

    assert "sandbox_redis:" in compose
    assert "REDIS_URL: redis://sandbox_redis:6379/0" in compose
    assert "sandbox_redis_data:/data" in compose

    assert "sandbox_files:/app/media" in compose
    assert "SANDBOX_MODE: \"true\"" in compose
    assert "SANDBOX_ROLE_SWITCH_ENABLED: \"true\"" in compose
    assert "SANDBOX_LOGIN_PHONE: \"12345678\"" in compose
    assert "SANDBOX_LOGIN_PASSWORD: \"1234567890\"" in compose

    assert "sandbox:\n    driver: bridge\n    internal: true" in compose
    assert "sandbox_backend:" in compose
    assert "sandbox_frontend:" in compose
    assert "sandbox_migrate:" in compose
    assert "sandbox_seed:" in compose


def test_sandbox_disables_live_background_and_external_runtime_actions():
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text()
    main = (REPOSITORY_ROOT / "apps" / "backend" / "main.py").read_text()

    assert "TREASURY_AUTO_SUBMIT_ENABLED: \"false\"" in compose
    assert "MIDNIGHT_REPORTS_ENABLED: \"false\"" in compose
    assert "COLLECTION_DAILY_REPORT_ENABLED: \"false\"" in compose
    assert "LELEFAPAYGATE_ENABLED: \"false\"" in compose
    assert "CALL_MEDIA_PROVIDER: disabled" in compose
    assert "ENABLE_ROLE_IMPERSONATION: \"false\"" in compose
    assert "if not settings.SANDBOX_MODE:" in main


def test_sandbox_public_routes_are_host_separated_from_production():
    caddy = (REPOSITORY_ROOT / "infra" / "caddy" / "Caddyfile").read_text()
    api_client = (REPOSITORY_ROOT / "apps" / "frontend" / "lib" / "api.ts").read_text()
    realtime = (REPOSITORY_ROOT / "apps" / "frontend" / "provider" / "realtimeProvider.tsx").read_text()

    assert "{$SANDBOX_APP_DOMAIN}" in caddy
    assert "reverse_proxy sandbox_frontend:3000" in caddy
    assert "{$SANDBOX_API_DOMAIN}" in caddy
    assert "reverse_proxy sandbox_backend:8000" in caddy
    assert 'X-Robots-Tag "noindex, nofollow, noarchive"' in caddy

    assert 'hostname.startsWith("sandbox.")' in api_client
    assert "api-sandbox.${rootDomain}/api/v1" in api_client
    assert "resolveApiBaseUrl()" in realtime


def test_sandbox_seed_is_guarded_and_contains_exactly_five_synthetic_clients():
    seed = (REPOSITORY_ROOT / "apps" / "backend" / "scripts" / "seed_sandbox.py").read_text()
    constants = _seed_constants()
    sample_clients = constants["SAMPLE_CLIENTS"]

    assert isinstance(sample_clients, tuple)
    assert len(sample_clients) == 5
    assert {item[0] for item in sample_clients} == {
        "59010001",
        "59010002",
        "59010003",
        "59010004",
        "59010005",
    }
    assert "if not settings.SANDBOX_MODE:" in seed
    assert '"loanhub", "loan_db", "production", "prod"' in seed
    assert 'source="sandbox_seed"' in seed
    assert 'status="active"' in seed
    for role in EXPECTED_COMPANY_ROLES:
        assert f'"{role}"' in seed


def test_sandbox_role_switch_and_login_ui_are_demo_only():
    router = (REPOSITORY_ROOT / "apps" / "backend" / "routers" / "sandbox.py").read_text()
    controls = (
        REPOSITORY_ROOT
        / "apps"
        / "frontend"
        / "components"
        / "sandbox"
        / "sandbox-banner.tsx"
    ).read_text()

    assert "if not settings.SANDBOX_MODE:" in router
    assert "settings.SANDBOX_ROLE_SWITCH_ENABLED" in router
    assert "user.phone != settings.SANDBOX_LOGIN_PHONE" in router
    assert 'prefix="/sandbox"' in router
    assert '@router.post("/switch-role")' in router

    assert 'const SANDBOX_PHONE = "12345678"' in controls
    assert 'const SANDBOX_PASSWORD = "1234567890"' in controls
    assert "PLATFORM_ROLES" in controls
    assert "COMPANY_ROLES" in controls
    assert '"borrower"' in controls
    assert "browserIsSandbox()" in controls
