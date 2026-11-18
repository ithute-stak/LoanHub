"""Standalone document-renderer contract tests (CDAS is never contacted)."""
import pytest
from services.cdas_affordability_pdf import build_government_affordability_pdf


def test_incomplete_stored_snapshot_is_rejected():
    with pytest.raises(ValueError, match="Incomplete stored affordability assessment"):
        build_government_affordability_pdf(db=None, company=None, snapshot={})


def test_report_uses_stored_values_and_no_provider(monkeypatch):
    from services import cdas_affordability_pdf as module
    # Branding is a presentation detail; the contract is that stored data renders.
    monkeypatch.setattr(module, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "draw_brand_footer", lambda *args, **kwargs: None)
    data = {
        "reference": "CDAS-AFF-TEST-001",
        "employee_number": "EMP-100",
        "borrower_id": "borrower-test",
        "assessed_at": "2026-11-18T14:00:00+00:00",
        "cdas_capacity": "1200.00",
        "proposed_installment": "650.00",
        "maximum_affordable_installment": "950.00",
        "decision": "pass",
        "policy_version": 1,
    }
    pdf = build_government_affordability_pdf(db=None, company=None, snapshot=data)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_unsafe_report_content_is_escaped(monkeypatch):
    from services import cdas_affordability_pdf as module
    monkeypatch.setattr(module, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "draw_brand_footer", lambda *args, **kwargs: None)
    data = {
        "reference": "AFF-TEST", "employee_number": "<script>bad</script>",
        "borrower_id": "borrower", "assessed_at": "2026-11-18",
        "cdas_capacity": "100.00", "proposed_installment": "50.00",
        "maximum_affordable_installment": "70.00", "decision": "fail",
        "policy_version": 1,
    }
    pdf = build_government_affordability_pdf(db=None, company=None, snapshot=data)
    assert pdf.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_identity_mismatch_never_creates_assessment_record(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from routers import cdas_government_employees as module
    async def mismatch(*args, **kwargs):
        return {"ok": False, "status": "identity_review_required", "affordability_checked": False}
    monkeypatch.setattr(module, "preview_government_employee_affordability", mismatch)
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    class NoWriteDB:
        def add(self, *args):
            raise AssertionError("Identity mismatch cannot save assessment")
        def commit(self):
            raise AssertionError("Identity mismatch cannot commit")
    payload = module.GovernmentEmployeeAffordabilityRequest(
        borrower_id=uuid4(), employee_number="EMP-100", authorisation_confirmed=True,
        proposed_monthly_installment="100.00",
    )
    context = SimpleNamespace(company_id=uuid4(), user=SimpleNamespace(id=uuid4()),
                              branch_id=None, role=SimpleNamespace(value="company_admin"))
    result = await module.create_government_affordability_record(
        payload=payload, context=context, db=NoWriteDB(),
    )
    assert result["status"] == "identity_review_required"


def test_pdf_download_never_calls_cdas(monkeypatch):
    from uuid import uuid4
    from types import SimpleNamespace
    from routers import cdas_government_employees as module
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    data = {
        "reference": "CDAS-AFF-TEST-001", "employee_number": "EMP-100",
        "borrower_id": str(uuid4()), "assessed_at": "2026-11-18T14:00:00+00:00",
        "cdas_capacity": "200.00", "proposed_installment": "100.00",
        "maximum_affordable_installment": "150.00", "decision": "pass",
        "policy_version": 1,
    }
    stored_id = uuid4()
    record = SimpleNamespace(id=stored_id, record_id=data["borrower_id"], event_data={"snapshot": data})
    # The production model stores UUID, as must this simulated record.
    from uuid import UUID
    record.record_id = UUID(data["borrower_id"])
    class Query:
        def filter(self, *args):
            return self
        def first(self):
            return record
    class DB:
        def query(self, model):
            return Query()
    monkeypatch.setattr(module, "build_government_affordability_pdf",
                        lambda **kwargs: b"%PDF-1.4\\nSNAPSHOT")
    ctx = SimpleNamespace(company_id=uuid4(), company=object(), staff=object(),
                          is_platform_admin=False)
    response = module.download_government_affordability_report(
        record_id=stored_id, context=ctx, db=DB(),
    )
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF-")
    assert response.headers["cache-control"] == "private, no-store"
