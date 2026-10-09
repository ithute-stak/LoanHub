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

    assert "Approved CDAS-enabled loan (optional)" in page
    assert "Prepare selected loan" in page
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
    assert "I confirm this employee authorised the payroll deduction." in page
    assert "LoanHub records this confirmation before the CDAS registration is sent." in page


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

    assert "<Label>Deduction Amount *</Label>" in page
    assert "<Label>No. of Months *</Label>" in page
    assert "Agency / Item Code" in page
    assert 'readOnly' in page
    assert "Approve & Register Deduction" in page
    assert "deduction_amount: lifecycle.deduction_amount" in page
    assert "deduction_period: lifecycle.total_installment" in page


def test_register_mode_matches_focused_cdas_add_deduction_flow() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert 'const isRegisterMode = requestedAction === "register" || requestedAction === "";' in page
    assert '{isRegisterMode ? "Add Deduction" : "CDAS deduction operations"}' in page
    assert "Create a new payroll deduction using the same business flow as CDAS" in page
    assert "New Deduction Application" in page
    assert "Employee / Loan" in page
    assert "Agency" in page
    assert "Deduction Details" in page
    assert "Deduction Amount *" in page
    assert "No. of Months *" in page
    assert "Approve & Register Deduction" in page
    assert "Principal Amt." in page
    assert "Expiry Month" in page
    assert "Policy / Loan Ref No" in page
    assert "generatedExpiryMonth" in page
    assert '{!isRegisterMode ? <Card id="modify-active"' in page
    assert '{!isRegisterMode ? <Card id="settle"' in page


def test_register_mode_keeps_only_amount_and_months_editable_in_cdas_style_form() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert 'value={lifecycle.item_code ? lifecycle.item_code : "Auto-generated from company CDAS profile"}' in page
    assert "directEmployeeNo.trim() && lifecycle.deduction_amount > 0 && lifecycle.total_installment > 0" in page
    assert "(lifecycle.deduction_amount * lifecycle.total_installment).toFixed(2)" in page
    assert 'value={lifecycle.effective_month || ""}' in page
    assert 'value={generatedExpiryMonth(lifecycle.effective_month, lifecycle.total_installment)}' in page
    assert 'value={lifecycle.reference_no || ""}' in page
    assert 'deduction_amount: Number(event.target.value)' in page
    assert 'total_installment: Number(event.target.value)' in page
    assert "Ready for deduction capture" in page


def test_direct_employee_registration_uses_loaded_employee_and_server_generated_fields() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert '@router.post("/deductions/direct-register")' in router
    assert "class CdasDirectEmployeeRegistrationRequest" in router
    assert "authorization_confirmed" in router
    assert "client.get_employee_details(employee_no)" in router
    assert "get_company_item_code(db, context.company_id)" in router
    assert "principal_amount = (payload.deduction_amount * payload.deduction_period)" in router
    assert "first_of_next_month" in router
    assert 'reference_no = f"LH-CDAS-' in router
    assert 'request_type=1' in router
    assert 'deduction_id=0' in router
    assert 'loan_policy=1' in router
    assert 'operation_type="deduction.lifecycle.1"' in router

    assert 'const requestedEmployeeNo = (searchParams.get("employee") || "").trim();' in page
    assert 'const [directEmployeeNo, setDirectEmployeeNo] = useState(requestedEmployeeNo);' in page
    assert 'id="cdas-direct-employee"' in page
    assert 'placeholder="e.g. 0019634"' in page
    assert '"/cdas/deductions/direct-register"' in page
    assert "employee_no: directEmployeeNo.trim()" in page
    assert "authorization_confirmed: borrowerConsentConfirmed" in page
    assert "Enter an employee number or prepare an approved loan" in page


def test_direct_registration_still_supports_approved_loan_mode() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "Approved CDAS-enabled loan (optional)" in page
    assert "Prepare selected loan" in page
    assert "/cdas/loans/${selectedLoanId}/register" in page
    assert "directEmployeeNo.trim()" in page
