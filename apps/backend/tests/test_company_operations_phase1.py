from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase_one_models_are_native_and_tenant_scoped():
    model = (ROOT / "backend" / "database" / "models" / "company_operations_phase1.py").read_text(encoding="utf-8")
    assert "class CRMRelationshipCase" in model
    assert "class CollateralAsset" in model
    assert "class LegalRecoveryMatter" in model
    assert "class CustomerComplaintCase" in model
    assert 'ComplaintCase = CustomerComplaintCase' in model
    assert "class CompanyOperationEvent" in model
    assert "company_id" in model
    assert "branch_id" in model
    assert "uq_crm_relationship_case_company_reference" in model
    assert "uq_collateral_asset_company_reference" in model
    assert "uq_legal_recovery_matter_company_reference" in model
    assert "uq_customer_complaint_case_company_reference" in model
    assert '__tablename__ = "customer_complaint_cases"' in model


def test_phase_one_migration_extends_current_reconciliation_head():
    migration = (ROOT / "backend" / "alembic" / "versions" / "p9v0x1z2a301_company_operations_phase1.py").read_text(encoding="utf-8")
    guards = (ROOT / "backend" / "alembic" / "versions" / "q0w1y2a3b401_company_operations_tenant_guards.py").read_text(encoding="utf-8")
    assert 'revision = "p9v0x1z2a301"' in migration
    assert 'down_revision = "n8u9w0y1z201"' in migration
    assert 'revision = "q0w1y2a3b401"' in guards
    assert 'down_revision = "p9v0x1z2a301"' in guards
    for table in ("crm_relationship_cases", "collateral_assets", "legal_recovery_matters", "customer_complaint_cases", "company_operation_events"):
        assert f'"{table}"' in migration


def test_database_guards_block_cross_tenant_borrowers_and_assignees():
    guards = (ROOT / "backend" / "alembic" / "versions" / "q0w1y2a3b401_company_operations_tenant_guards.py").read_text(encoding="utf-8")
    assert "enforce_company_operation_borrower_scope" in guards
    assert "company_borrower_accounts" in guards
    assert "client_company_loan" in guards
    assert "Borrower is outside the active company scope" in guards
    assert "enforce_company_operation_assignee_scope" in guards
    assert "company_staff" in guards
    assert "staff.is_active IS TRUE" in guards
    assert "Assigned user is outside the active company/branch scope" in guards
    assert "customer_complaint_cases" in guards


def test_native_api_exposes_operational_workflows_and_guardrails():
    source = (ROOT / "backend" / "routers" / "company_operations_phase1.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/company-operations"' in source
    assert '@router.get("/overview")' in source
    assert '@router.post("/crm", status_code=201)' in source
    assert '@router.post("/crm/{case_id}/contact")' in source
    assert '@router.post("/collateral", status_code=201)' in source
    assert '@router.post("/collateral/{asset_id}/request-release")' in source
    assert '@router.post("/collateral/{asset_id}/release")' in source
    assert "Collateral cannot be released while the linked loan still has an outstanding balance" in source
    assert '@router.post("/legal", status_code=201)' in source
    assert '@router.post("/legal/{matter_id}/stage")' in source
    assert '@router.post("/complaints", status_code=201)' in source
    assert '@router.post("/complaints/{case_id}/acknowledge")' in source
    assert '@router.post("/complaints/{case_id}/escalate")' in source
    assert '@router.post("/complaints/{case_id}/resolve")' in source
    assert 'company_operations_phase1.router' in api_router


def test_append_only_event_evidence_is_recorded_for_material_actions():
    source = (ROOT / "backend" / "routers" / "company_operations_phase1.py").read_text(encoding="utf-8")
    for event in ("created", "contact_recorded", "registered", "release_requested", "released", "matter_opened", "stage_updated", "complaint_opened", "acknowledged", "escalated", "resolved"):
        assert f'"{event}"' in source
    assert "CompanyOperationEvent(" in source


def test_complaints_have_sla_and_regulatory_attention_signals():
    source = (ROOT / "backend" / "routers" / "company_operations_phase1.py").read_text(encoding="utf-8")
    assert "sla_due_at" in source
    assert "sla_breached" in source
    assert "regulatory_reportable" in source
    assert "timedelta(hours=payload.sla_hours)" in source


def test_frontend_workspace_surfaces_all_four_native_registers():
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "operations" / "page.tsx").read_text(encoding="utf-8")
    client = (ROOT / "frontend" / "api" / "companyOperations.ts").read_text(encoding="utf-8")
    command = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")
    assert "Specialised Company Operations" in page
    assert "CRM relationship cases" in page
    assert "Collateral register" in page
    assert "Legal recovery matters" in page
    assert "Complaint cases" in page
    assert '"/company-operations/overview"' in client
    assert 'href="/company/operations"' in command
    assert "Specialised Operations" in command
