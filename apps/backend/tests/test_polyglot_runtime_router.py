from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_platform_runtime_status_is_admin_only_and_explains_authority() -> None:
    router = (ROOT / "routers/polyglot_runtime.py").read_text(encoding="utf-8")
    api = (ROOT / "api/v1/router.py").read_text(encoding="utf-8")
    compose = ROOT.parents[1].joinpath("compose.workers.yaml").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/runtime"' in router
    assert '@router.get("/workers/status")' in router
    assert "Depends(require_platform_admin)" in router
    assert '"authority": "python"' in router
    assert '"loan_decisions": "python_authoritative"' in router
    assert '"worker_failure_mode": "python_fallback_for_delegated_safe_work"' in router

    assert "polyglot_runtime" in api
    assert "polyglot_runtime.router" in api

    assert "LOANHUB_RUST_COMPUTE_URL: http://rust-compute:8082" in compose
    assert "LOANHUB_GO_WORKER_URL: http://go-worker:8081" in compose


def test_platform_runtime_monitor_surfaces_worker_health_and_fallbacks() -> None:
    page = ROOT.parents[1].joinpath(
        "apps/frontend/app/(dashboard)/superadmin/runtime/page.tsx"
    ).read_text(encoding="utf-8")
    dashboard = ROOT.parents[1].joinpath(
        "apps/frontend/app/(dashboard)/superadmin/page.tsx"
    ).read_text(encoding="utf-8")

    assert "Polyglot work-sharing monitor" in page
    assert 'api.get<RuntimeStatus>("/runtime/workers/status")' in page
    assert "Circuit open" in page
    assert "Parity mismatches" in page
    assert "Python fallback" in page
    assert 'href="/superadmin/runtime"' in dashboard
