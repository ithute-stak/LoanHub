from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from services.collection_automation_service import DEFAULT_STRATEGY, _band, _priority


ROOT = Path(__file__).resolve().parents[2]


class CaseStub:
    days_past_due = 15
    overdue_amount = Decimal("2500.00")
    priority = "normal"


def test_default_treatment_strategy_covers_full_arrears_lifecycle():
    assert _band(DEFAULT_STRATEGY, 1)["treatment"] == "EARLY_CONTACT"
    assert _band(DEFAULT_STRATEGY, 15)["treatment"] == "INTENSIVE_CONTACT"
    assert _band(DEFAULT_STRATEGY, 45)["treatment"] == "FORMAL_DEFAULT"
    assert _band(DEFAULT_STRATEGY, 90)["treatment"] == "LEGAL_READINESS"
    assert _band(DEFAULT_STRATEGY, 0)["treatment"] == "EARLY_CONTACT"


def test_broken_promise_increases_recovery_priority():
    normal_score, _ = _priority(CaseStub(), broken_promise=False, recovery_path="direct_collection")
    broken_score, _ = _priority(CaseStub(), broken_promise=True, recovery_path="direct_collection")
    assert broken_score > normal_score


def test_collections_automation_schema_is_tenant_scoped_and_versioned():
    model = (ROOT / "backend" / "database" / "models" / "collection_automation.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "i3p4r5t6u701_automated_collections_recovery.py").read_text(encoding="utf-8")
    versioning = (ROOT / "backend" / "alembic" / "versions" / "i3p4r5t6u702_collection_policy_versioning.py").read_text(encoding="utf-8")
    assert 'ForeignKey("loan_companies.id", ondelete="CASCADE")' in model
    assert "uq_collection_work_item_case_dedup" in model
    assert "uq_collection_treatment_policy_company_name_version" in model
    assert 'down_revision = "h2n3q4s5t601"' in migration
    assert 'down_revision = "i3p4r5t6u701"' in versioning


def test_recovery_engine_explicitly_detects_broken_promises_collection_paths_and_stale_work():
    source = (ROOT / "backend" / "services" / "collection_automation_service.py").read_text(encoding="utf-8")
    assert 'case.promise_status = "broken"' in source
    assert 'return "cdas_recovery" if active else "cdas_registration_review"' in source
    assert 'return "employer_payroll_recovery"' in source
    assert 'return "direct_collection"' in source
    assert "legal_readiness" in source
    assert '"default_notice_recorded"' in source
    assert '"recovery_contact_attempted"' in source
    assert 'CollectionWorkItem.status: "cancelled"' in source
    assert "run_scheduled_collection_automation" in source
    assert "Treatment DPD bands must not overlap" in source


def test_recovery_api_exposes_queue_policy_engine_assignment_and_controlled_legal_escalation():
    source = (ROOT / "backend" / "routers" / "collection_automation.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/collections/automation"' in source
    assert '@router.get("/dashboard")' in source
    assert '@router.post("/run")' in source
    assert '@router.get("/policy")' in source
    assert '@router.put("/policy")' in source
    assert '@router.get("/work-items")' in source
    assert '@router.put("/work-items/{item_id}/assignment")' in source
    assert "The selected assignee is not active staff in this company/branch" in source
    assert '@router.get("/cases/{case_id}/legal-readiness")' in source
    assert '@router.post("/cases/{case_id}/escalate-legal")' in source
    assert "require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)" in source
    assert 'activity_type="legal_handover"' in source
    assert "collection_automation.router" in router


def test_maintenance_worker_runs_automation_on_its_own_daily_schedule():
    config = (ROOT / "backend" / "database" / "config" / "config.py").read_text(encoding="utf-8")
    maintenance = (ROOT / "backend" / "docker" / "maintenance.py").read_text(encoding="utf-8")
    assert "COLLECTION_AUTOMATION_ENABLED: bool = True" in config
    assert "COLLECTION_AUTOMATION_HOUR: int = 0" in config
    assert "COLLECTION_AUTOMATION_MINUTE: int = 15" in config
    assert "run_scheduled_collection_automation" in maintenance
    assert "last_collection_automation_date" in maintenance
    assert "_seconds_until_next_collection_automation" in maintenance


def test_collections_frontend_surfaces_strategy_queue_paths_legal_readiness_and_productivity():
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "collections" / "automation" / "page.tsx").read_text(encoding="utf-8")
    layout = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "collections" / "layout.tsx").read_text(encoding="utf-8")
    assert "Automated Collections & Recovery Engine" in page
    assert "DPD treatment strategy" in page
    assert "Save new version" in page
    assert "Prioritised collector queue" in page
    assert "Broken promises" in page
    assert "Legal readiness" in page
    assert "Collector productivity" in page
    assert "/company/collections/automation" in layout
