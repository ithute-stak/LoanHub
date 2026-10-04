from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cdas_application_employee_verification_links_verified_payroll_profile() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    lending = _read(ROOT / "routers/professional_lending.py")

    assert '@router.post("/applications/{application_id}/verify-employee")' in router
    assert "client.get_employee_details(payload.employee_no)" in router
    assert "returned_employee_no.casefold() != requested_employee_no.casefold()" in router
    assert "CDASPayrollProfile(" in router
    assert "profile.verified = True" in router
    assert "profile.verified_at = datetime.now(timezone.utc)" in router
    assert "Verified using CDAS /api/employee/getDetails (Third Party API v1.5)." in router

    assert "CDASPayrollProfile.verified.is_(True)" in lending
    assert "A verified CDAS payroll profile with an employee number is required" in lending


def test_cdas_company_item_code_is_stored_for_provider_registration() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    service = _read(ROOT / "services/cdas_config_service.py")
    settings = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/settings/_components/company-cdas-settings.tsx"
    )

    assert "item_code: str | None" in router
    assert "item_code=payload.item_code" in router
    assert '"item_code": item_code' in service
    assert 'id="cdas-item-code"' in settings
    assert "Issued by CDAS / DataNet" in settings


def test_cdas_approved_loan_registration_draft_is_local_and_provider_safe() -> None:
    router = _read(ROOT / "routers/cdas_api.py")

    assert '@router.get("/loans/{loan_id}/registration-draft")' in router
    assert '"request_type": 1' in router
    assert '"deduction_id": 0' in router
    assert '"loan_policy": 1' in router
    assert '"item_code": item_code' in router
    assert '"deduction_amount": str(loan.installment_amount or 0)' in router
    assert '"total_installment": int(loan.repayment_period or 0)' in router
    assert '"principal_amount": str(loan.principal_amount or 0)' in router
    assert '"reference_no": loan.loan_reference' in router
    assert '"provider_request_sent": False' in router
    assert "client.add_update_deduction" not in router.split(
        '@router.get("/loans/{loan_id}/registration-draft")', 1
    )[1].split('@router.get("/operations")', 1)[0]


def test_cdas_workspace_can_manually_link_verification_to_application() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/page.tsx")

    assert "Load applications" in page
    assert "Loan application (optional)" in page
    assert "/cdas/applications/${selectedApplicationId}/verify-employee" in page
    assert "Payroll profile linked to this application" in page
    assert "useEffect" not in page

def test_cdas_operations_prepare_registration_from_approved_loanhub_loan() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "Load approved loans" in page
    assert "Prepare registration" in page
    assert "professionalApi.listDirect()" in page
    assert "application.cdas_collection_enabled" in page
    assert "/cdas/loans/${selectedLoanId}/registration-draft" in page
    assert "No CDAS request has been sent." in page
    assert "confirmed: false" in page
    assert 'api.post<MutationResponse>("/cdas/deductions/lifecycle", lifecycle)' in page
