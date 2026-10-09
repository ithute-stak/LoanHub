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


def test_cdas_item_code_is_platform_owned_for_provider_registration() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    service = _read(ROOT / "services/cdas_config_service.py")
    platform_router = _read(ROOT / "routers/platform_cdas.py")
    settings = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/settings/_components/company-cdas-settings.tsx"
    )

    assert "get_company_item_code(db, company_id)" in router
    assert "profile.item_code" in service
    assert "item_code: str | None" in platform_router
    assert "item_code=payload.item_code" in platform_router
    assert 'id="cdas-item-code"' not in settings
    assert "credentials are held securely by the LoanHub Platform Owner" in settings


def test_cdas_approved_loan_registration_draft_is_local_and_provider_safe() -> None:
    router = _read(ROOT / "routers/cdas_api.py")

    assert '@router.get("/loans/{loan_id}/registration-draft")' in router
    assert "request_type=1" in router
    assert "deduction_id=0" in router
    assert "loan_policy=1" in router
    assert "item_code=item_code" in router
    assert "deduction_amount=loan.installment_amount or 0" in router
    assert "total_installment=int(loan.repayment_period or 0)" in router
    assert "principal_amount=loan.principal_amount or 0" in router
    assert "reference_no=loan.loan_reference" in router
    assert '"provider_request_sent": False' in router
    draft_block = router.split(
        '@router.get("/loans/{loan_id}/registration-draft")', 1
    )[1].split('@router.post("/loans/{loan_id}/register")', 1)[0]
    assert "client.add_update_deduction" not in draft_block


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


def test_confirmed_loan_registration_persists_official_cdas_provider_link() -> None:
    router = _read(ROOT / "routers/cdas_api.py")

    assert '@router.post("/loans/{loan_id}/register")' in router
    assert "CdasOfficialMandateState" in router
    assert "CdasOfficialMandateEvent" in router
    assert "CDASDeductionMandate" in router
    assert "borrower_consent" in router
    assert 'operation_type="deduction.lifecycle.1"' in router
    assert "state.deduction_id = deduction_id" in router
    assert 'state.lifecycle_status = "registered" if reconciled else "registration_pending"' in router
    assert "mandate.external_reference = str(deduction_id)" in router
    assert 'event_type="registration"' in router


def test_registration_ui_uses_linked_loan_endpoint_and_requires_borrower_consent() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "/cdas/loans/${selectedLoanId}/register" in page
    assert "borrower_consent: borrowerConsentConfirmed" in page
    assert "I confirm the borrower authorised payroll deduction for this loan." in page
    assert "LoanHub records this confirmation on the CDAS mandate before registration is sent." in page


def test_linked_cdas_lifecycle_uses_stored_provider_identifiers() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert '@router.get("/loans/{loan_id}/state")' in router
    assert '@router.post("/loans/{loan_id}/lifecycle")' in router
    assert "if not state or not state.deduction_id" in router
    assert "Reconcile the previous CDAS operation before submitting another lifecycle change" in router
    assert "deduction_id=int(state.deduction_id)" in router
    assert "employee_no=mandate.employee_number" in router
    assert "item_code=state.item_code" in router
    assert 'status_by_request = {3: ("reviewed", 3), 4: ("approved", 4), 6: ("cancelled", 6), 10: ("changed", 10)}' in router

    assert "Load linked state" in page
    assert "/cdas/loans/${selectedLoanId}/state" in page
    assert "/cdas/loans/${selectedLoanId}/lifecycle" in page
    assert "DeductionID {linkedState.deduction_id ?? \"pending\"}" in page


def test_linked_cdas_modify_and_settlement_use_saved_provider_identity() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert '@router.post("/loans/{loan_id}/modify-active")' in router
    assert '@router.post("/loans/{loan_id}/settle")' in router
    assert "deduction_id=int(state.deduction_id)" in router
    assert "employee_no=mandate.employee_number" in router
    assert "item_code=state.item_code" in router
    assert 'operation_type="deduction.modify_active"' in router
    assert 'operation_type="deduction.settle"' in router
    assert 'state.lifecycle_status = "changed" if reconciled else "change_pending"' in router
    assert 'state.lifecycle_status = "settled" if reconciled else "settlement_pending"' in router

    assert "/cdas/loans/${selectedLoanId}/modify-active" in page
    assert "/cdas/loans/${selectedLoanId}/settle" in page
    assert "setModify((current) => ({" in page
    assert "setSettle((current) => ({" in page



def test_cdas_collected_loan_requires_reconciled_provider_mandate_before_disbursement() -> None:
    service = _read(ROOT / "services/loan_service.py")

    assert "def assert_disbursement_governance_ready(" in service
    assert "CDASDeductionMandate" in service
    assert "CdasOfficialMandateState" in service
    assert 'usable_mandate_statuses = {"registered", "approved", "active"}' in service
    assert 'usable_lifecycle_statuses = {"registered", "approved", "active"}' in service
    assert "state.deduction_id is None" in service
    assert "bool(state.requires_reconciliation)" in service
    assert "Register the mandate before disbursement." in service
    assert "Complete provider registration/reconciliation" in service


def test_cdas_registration_requires_only_amount_and_period_from_operator() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "deduction_amount: Decimal = Field(gt=Decimal(\"0\")" in router
    assert "deduction_period: int = Field(gt=0, le=600)" in router
    assert 'provider_request["DeductionAmount"] = payload.deduction_amount' in router
    assert 'provider_request["TotalInstallment"] = payload.deduction_period' in router
    assert "monthly_deduction=payload.deduction_amount" in router
    assert "expected_installments=payload.deduction_period" in router

    assert "<Label>Deduction amount</Label>" in page
    assert "<Label>Deduction period</Label>" in page
    assert "LoanHub will generate the CDAS registration" in page
    assert "Auto-generated" in page
    assert "Approve & Register Deduction" in page
    assert "deduction_amount: lifecycle.deduction_amount" in page
    assert "deduction_period: lifecycle.total_installment" in page
