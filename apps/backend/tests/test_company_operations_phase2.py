from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase_two_models_are_native_and_company_scoped():
    source = (ROOT / "backend" / "database" / "models" / "company_operations_phase2.py").read_text(encoding="utf-8")
    for symbol in (
        "class ProcurementVendor",
        "class ProcurementRequest",
        "class CompanyBudgetPlan",
        "class CompanyBudgetLine",
        "class InternalAuditEngagement",
        "class InternalAuditFinding",
    ):
        assert symbol in source
    for table in (
        "procurement_vendors",
        "procurement_requests",
        "company_budget_plans",
        "company_budget_lines",
        "internal_audit_engagements",
        "internal_audit_findings",
    ):
        assert f'__tablename__ = "{table}"' in source
    assert "company_id" in source
    assert "branch_id" in source


def test_phase_two_migration_extends_phase_one_guard_head():
    migration = (ROOT / "backend" / "alembic" / "versions" / "r1x2z3b4c501_company_operations_phase2.py").read_text(encoding="utf-8")
    assert 'revision = "r1x2z3b4c501"' in migration
    assert 'down_revision = "q0w1y2a3b401"' in migration
    for table in (
        "procurement_vendors",
        "procurement_requests",
        "company_budget_plans",
        "company_budget_lines",
        "internal_audit_engagements",
        "internal_audit_findings",
    ):
        assert f'"{table}"' in migration


def test_phase_two_api_has_controlled_procurement_budget_and_audit_workflows():
    source = (ROOT / "backend" / "routers" / "company_operations_phase2.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/company-operations-phase2"' in source
    assert '@router.post("/vendors", status_code=201)' in source
    assert '@router.post("/procurement", status_code=201)' in source
    assert '@router.post("/procurement/{request_id}/submit")' in source
    assert '@router.post("/procurement/{request_id}/approve")' in source
    assert "Only submitted requests can be approved" in source
    assert '@router.post("/budgets", status_code=201)' in source
    assert '@router.post("/budgets/{plan_id}/lines", status_code=201)' in source
    assert '@router.post("/budgets/{plan_id}/approve")' in source
    assert "Approved budgets are locked" in source
    assert "A budget must contain at least one line before approval" in source
    assert '@router.post("/audits", status_code=201)' in source
    assert '@router.post("/audits/{engagement_id}/findings", status_code=201)' in source
    assert '@router.post("/audits/{engagement_id}/close")' in source
    assert "Audit cannot close while findings remain open" in source
    assert "company_operations_phase2.router" in api_router


def test_management_gate_is_required_for_material_approvals_and_closure():
    source = (ROOT / "backend" / "routers" / "company_operations_phase2.py").read_text(encoding="utf-8")
    assert "COMPANY_MANAGEMENT_ROLES" in source
    assert "Company management approval is required" in source
    assert source.count("_management(context)") >= 3
