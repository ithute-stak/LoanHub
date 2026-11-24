"""Regression coverage for tenant-owned CDAS affordability PDF issuance."""
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from services import client_cdas_affordability_pdf as pdf_service


def test_cdas_affordability_pdf_contains_provider_snapshot(monkeypatch):
    monkeypatch.setattr(pdf_service, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf_service, "draw_brand_footer", lambda *args, **kwargs: None)
    data = pdf_service.build_client_cdas_affordability_pdf(
        db=None, company=None, client_name="Test Borrower",
        client_reference="CLI-TEST-001", employee_no="EMP-876",
        employee={"EmployeeNo": "EMP-876", "Name": "Test", "Surname": "Borrower",
                  "Department": "Education", "DOB": "1990-01-01"},
        affordability=Decimal("2450.00"),
        deductions=[{"AgencyName": "Example lender", "DeductionStatusName": "Active",
                     "DeductionAmount": "250.00"}],
        assessed_at=datetime(2026, 11, 24, 7, 0, tzinfo=timezone.utc),
        reference="CDAS-AFF-TEST-001", environment="test",
    )
    assert data.startswith(b"%PDF-")
    extracted = " ".join(" ".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages).split())
    for expected in ("Test Borrower", "EMP-876", "2,450.00",
                     "Example lender", "250.00", "CDAS-AFF-TEST-001",
                     "not a loan approval"):
        assert expected.lower() in extracted.lower()


def test_cdas_pdf_route_enforces_tenant_identity_and_managed_documents():
    root = Path(__file__).parents[1]
    cdas = (root / "routers" / "cdas_api.py").read_text(encoding="utf-8")
    clients = (root / "routers" / "company_clients.py").read_text(encoding="utf-8")
    section = cdas.split('@router.post("/clients/{account_id}/affordability-report"')[1].split('@router.post("/employees/affordability")')[0]
    assert "_require_lending_user(context)" in section
    assert "company_id=context.company_id" in section
    assert "assert_branch_scope(context, account.branch_id)" in section
    assert "CDASPayrollProfile.borrower_id == account.borrower_id" in section
    assert "returned_no.casefold() != employee_no.casefold()" in section
    assert "client.check_affordability(employee_no)" in section
    assert "client.view_all_deductions(employee_no)" in section
    assert 'category="borrower_cdas_affordability"' in section
    assert 'linked_entity_type="company_borrower_account"' in section
    assert "is_confidential=True" in section
    assert "db.commit()" in section
    assert '"cdas_affordability": "borrower_cdas_affordability"' in clients


def test_client_profile_issues_server_generated_pdf_and_refreshes_documents():
    root = Path(__file__).parents[2]
    dialog = (root / "frontend" / "components" / "clients" / "company-client-profile-dialog.tsx").read_text(encoding="utf-8")
    api = (root / "frontend" / "api" / "companyClients.ts").read_text(encoding="utf-8")
    assert "issueCompanyClientCdasAffordabilityPdf(clientId)" in dialog
    assert "await getCompanyClientProfile(clientId)" in dialog
    assert "await downloadCompanyClientFile(clientId" in dialog
    assert "Generate and save PDF" in dialog
    assert '"/cdas/employees/affordability"' in dialog
    assert "/cdas/clients/" in api or "/clients/" in api
    assert "affordability-report" in api


def test_legacy_payroll_identity_can_issue_report_without_employment_type_field():
    """A tenant-linked payroll profile must work for older imported clients."""
    root = Path(__file__).parents[1]
    source = (root / "routers" / "cdas_api.py").read_text(encoding="utf-8")
    endpoint = source.split('@router.post("/clients/{account_id}/affordability-report"')[1].split('@router.post("/employees/affordability")')[0]
    assert "CDASPayrollProfile.company_id == context.company_id" in endpoint
    assert "CDASPayrollProfile.borrower_id == account.borrower_id" in endpoint
    assert "returned_no.casefold() != employee_no.casefold()" in endpoint
    assert "account.borrower, \"employment_type\"" not in endpoint
    assert "assert_branch_scope(context, account.branch_id)" in endpoint


def _report_runtime_fixture(monkeypatch):
    """Use no real CDAS credentials, client data, object storage, or database."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4

    from routers import cdas_api

    company_id, branch_id, account_id, borrower_id, user_id = (uuid4() for _ in range(5))
    person = SimpleNamespace(first_name="Test", middle_name=None, last_name="Borrower")
    borrower = SimpleNamespace(id=borrower_id, user=SimpleNamespace(person=person))
    account = SimpleNamespace(
        id=account_id, borrower_id=borrower_id, borrower=borrower,
        branch_id=branch_id, account_reference="CLIENT-TEST", company_id=company_id,
        company=SimpleNamespace(id=company_id),
    )
    context = SimpleNamespace(company_id=company_id, user=SimpleNamespace(id=user_id))
    profile = SimpleNamespace(employee_number="EMP-876")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = profile
    provider = SimpleNamespace(
        get_employee_details=AsyncMock(return_value={"EmployeeNo": "EMP-876", "Name": "Test"}),
        check_affordability=AsyncMock(return_value="2450.00"),
        view_all_deductions=AsyncMock(return_value=[{"AgencyName": "Example", "Amount": "250.00"}]),
    )
    monkeypatch.setattr(cdas_api, "_require_lending_user", lambda ctx: None)
    monkeypatch.setattr(cdas_api, "assert_branch_scope", lambda *args: None)
    monkeypatch.setattr(cdas_api, "company_client_or_404", lambda *args, **kwargs: account)
    monkeypatch.setattr(cdas_api, "get_company_cdas_client", lambda *args: provider)
    monkeypatch.setattr(cdas_api, "_prepare_cdas_business_operation", lambda *args, **kwargs: "test")
    operations = []
    monkeypatch.setattr(
        cdas_api, "_record_cdas_business_operation",
        lambda *args, **kwargs: operations.append(kwargs["operation_type"]),
    )
    pdf = b"%PDF-1.4\n%%EOF"
    monkeypatch.setattr(cdas_api, "build_client_cdas_affordability_pdf", lambda **kwargs: pdf)
    stored = []
    record = SimpleNamespace(id=uuid4(), original_name="stored.pdf")
    def save(*args, **kwargs):
        stored.append(kwargs)
        return record
    monkeypatch.setattr(cdas_api, "store_bytes", save)
    return SimpleNamespace(
        api=cdas_api, db=db, context=context, account=account, profile=profile,
        provider=provider, operations=operations, stored=stored, pdf=pdf,
    )


def test_cdas_pdf_issuance_saves_tenant_scoped_confidential_document(monkeypatch):
    import asyncio
    from decimal import Decimal

    env = _report_runtime_fixture(monkeypatch)
    response = asyncio.run(env.api.issue_client_cdas_affordability_report(
        account_id=env.account.id, context=env.context, db=env.db,
    ))
    assert response["ok"] is True
    assert response["affordability"] == "2450.00"
    assert response["deduction_count"] == 1
    assert env.operations == ["employee_verification", "affordability", "deduction_lookup"]
    assert len(env.stored) == 1
    saved = env.stored[0]
    assert saved["content"] == env.pdf
    assert saved["company_id"] == env.context.company_id
    assert saved["branch_id"] == env.account.branch_id
    assert saved["linked_entity_type"] == "company_borrower_account"
    assert saved["linked_entity_id"] == str(env.account.id)
    assert saved["category"] == "borrower_cdas_affordability"
    assert saved["visibility"] == "private"
    assert saved["is_confidential"] is True
    env.db.commit.assert_called_once()


def test_cdas_pdf_rejects_employee_identity_mismatch_before_affordability_or_storage(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException

    env = _report_runtime_fixture(monkeypatch)
    env.provider.get_employee_details.return_value = {"EmployeeNo": "OTHER-EMPLOYEE"}
    with pytest.raises(HTTPException) as err:
        asyncio.run(env.api.issue_client_cdas_affordability_report(
            account_id=env.account.id, context=env.context, db=env.db,
        ))
    assert err.value.status_code == 502
    env.provider.check_affordability.assert_not_awaited()
    env.provider.view_all_deductions.assert_not_awaited()
    assert env.stored == []
    env.db.commit.assert_not_called()


def test_cdas_pdf_missing_payroll_identity_does_not_contact_provider(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException

    env = _report_runtime_fixture(monkeypatch)
    env.db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as err:
        asyncio.run(env.api.issue_client_cdas_affordability_report(
            account_id=env.account.id, context=env.context, db=env.db,
        ))
    assert err.value.status_code == 409
    env.provider.get_employee_details.assert_not_awaited()
    assert env.stored == []
    env.db.commit.assert_not_called()
