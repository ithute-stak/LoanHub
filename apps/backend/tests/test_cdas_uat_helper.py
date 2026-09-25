from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "scripts" / "cdas-uat-local.sh"
RUNBOOK = ROOT / "docs" / "cdas-uat-runbook.md"


def test_cdas_uat_helper_is_isolated_and_local_only() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert 'PROJECT_NAME="loanhub-cdas-uat"' in source
    assert "DB_NAME=loanhub_cdas_uat" in source
    assert "ENVIRONMENT=development" in source
    assert "NEXT_PUBLIC_API_URL=http://localhost:18000/api/v1" in source
    assert "PUBLIC_APP_URL=http://localhost:13000" in source
    assert "CORS_ORIGINS=http://localhost:13000" in source


def test_cdas_uat_helper_never_starts_background_maintenance() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "compose up -d --build db redis migrate backend frontend" in source
    assert "compose up -d --build db redis migrate backend frontend maintenance" not in source
    assert "Maintenance worker was intentionally NOT started." in source


def test_cdas_uat_helper_does_not_embed_provider_credentials() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "CDAS_USERNAME=" not in source
    assert "CDAS_PASSWORD=" not in source
    assert "lelefa.api.user" not in source
    assert "test-cdas-thirdpartyapi.sentraptt.com" not in source
    assert "CDAS provider credentials are NOT stored by this script." in source


def test_cdas_uat_start_is_one_command_with_preflight_and_readiness_wait() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "start_uat()" in source
    assert "require_command openssl" in source
    assert "require_command curl" in source
    assert "require_docker" in source
    assert "wait_for_backend" in source
    assert "for attempt in $(seq 1 60)" in source
    assert "seed_uat" in source
    assert "status_uat" in source
    assert "start) start_uat ;;" in source


def test_cdas_uat_shutdown_preserves_volumes() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "compose down\n" in source
    assert "compose down -v" not in source
    assert "Volumes were preserved." in source


def test_uat_runbook_keeps_mutations_after_read_acceptance() -> None:
    source = RUNBOOK.read_text(encoding="utf-8")

    read_gate = source.index("## Gate C: employee verification")
    mutation_gate = source.index("## Gate G: controlled deduction lifecycle")
    assert read_gate < mutation_gate
    assert "bash scripts/cdas-uat-local.sh start" in source
    assert "must not automatically replay that write" in source
    assert "PR #78 must remain unmerged" in source
