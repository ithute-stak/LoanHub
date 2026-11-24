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
