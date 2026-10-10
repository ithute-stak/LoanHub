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

    assert "Employee and LoanHub loan" in page
    assert "/cdas/employees/registration-context" in page
    assert "/cdas/loans/${loanId}/registration-draft" in page
    assert "matched_loan" in page
    assert "No loan means no deduction registration." in page
    assert "useEffect" not in page
    assert "professionalApi.listDirect()" not in page
    assert "Approved CDAS-enabled loan (optional)" not in page
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


def test_cdas_registration_requires_only_monthly_amount_from_operator() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert 'deduction_amount: Decimal = Field(gt=Decimal("0")' in router
    assert "deduction_period: int | None" in router
    assert 'provider_request["DeductionAmount"] = payload.deduction_amount' in router
    assert 'provider_request["TotalInstallment"] = deduction_period' in router
    assert "monthly_deduction=payload.deduction_amount" in router
    assert "expected_installments=deduction_period" in router
    assert "_auto_deduction_period(" in router

    assert "<Label>Deduction Amount *</Label>" in page
    assert "<Label>No. of Months</Label>" in page
    assert "Calculated from loan amount" in page
    assert "readOnly" in page
    assert "Approve & Register Deduction" in page
    assert "deduction_amount: lifecycle.deduction_amount" in page
    assert "deduction_period: lifecycle.total_installment" not in page

def test_register_mode_matches_focused_cdas_add_deduction_flow() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert 'const isRegisterMode = requestedAction === "register" || requestedAction === "";' in page
    assert '{isRegisterMode ? "Add Deduction" : "CDAS deduction operations"}' in page
    assert "New Deduction Application" in page
    assert "Employee / Loan" in page
    assert "Affordability" in page
    assert "Agency" in page
    assert "Deduction Details" in page
    assert "Deduction Amount *" in page
    assert "No. of Months" in page
    assert "Approve & Register Deduction" in page
    assert "Principal Amt." in page
    assert "Expiry Month" in page
    assert "Policy / Loan Ref No" in page
    assert "generatedExpiryMonth" in page
    assert '{!isRegisterMode ? <Card id="modify-active"' in page
    assert '{!isRegisterMode ? <Card id="settle"' in page

def test_register_mode_keeps_only_amount_editable_and_calculates_months() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert 'value={lifecycle.item_code ? lifecycle.item_code : "Auto-generated from company CDAS profile"}' in page
    assert "Math.ceil(lifecycle.principal_amount / amount)" in page
    assert "value={calculatedMonths || \"\"}" in page
    assert "Auto-calculated as loan principal ÷ monthly deduction, rounded up." in page
    assert 'value={lifecycle.effective_month || ""}' in page
    assert "generatedExpiryMonth(lifecycle.effective_month, calculatedMonths)" in page
    assert 'value={lifecycle.reference_no || ""}' in page
    assert "max={affordability > 0 ? affordability : undefined}" in page
    assert "amountExceedsAffordability" in page
    assert "Ready for deduction capture" in page

def test_employee_registration_requires_affordability_and_matched_loanhub_loan() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert '@router.post("/employees/registration-context")' in router
    assert "_matching_cdas_loan_for_employee(" in router
    assert "ClientCompanyLoan.borrower_id == profile.borrower_id" in router
    assert "ClientCompanyLoan.cdas_collection_enabled.is_(True)" in router
    assert "LoanStatus.APPROVED" in router
    assert "LoanStatus.ACTIVE" in router
    assert "await client.check_affordability(employee_no)" in router
    assert '"can_register": profile is not None and loan is not None' in router
    assert "No eligible approved or active CDAS-enabled LoanHub loan was found for this employee" in router

    assert 'const requestedEmployeeNo = (searchParams.get("employee") || "").trim();' in page
    assert 'const [directEmployeeNo, setDirectEmployeeNo] = useState(requestedEmployeeNo);' in page
    assert 'id="cdas-direct-employee"' in page
    assert 'placeholder="e.g. 0019634"' in page
    assert '"/cdas/employees/registration-context"' in page
    assert "Verify & Find Loan" in page
    assert "Maximum monthly deduction" in page
    assert "No eligible loan" in page

def test_employee_registration_auto_uses_matched_approved_loan() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "const matchedLoan = employeeContext?.matched_loan ?? null;" in page
    assert "const loanId = resolved.matched_loan.loan_id;" in page
    assert "setSelectedLoanId(loanId)" in page
    assert "/cdas/loans/${loanId}/registration-draft" in page
    assert "/cdas/loans/${selectedLoanId}/register" in page
    assert "Select a loan" not in page


def test_cdas_registration_enforces_live_affordability_and_server_calculated_period() -> None:
    router = _read(ROOT / "routers/cdas_api.py")

    assert "affordability = Decimal(str(await client.check_affordability(profile.employee_number)))" in router
    assert "if payload.deduction_amount > affordability:" in router
    assert "Deduction amount cannot exceed the employee's CDAS affordability" in router
    assert "principal_amount = Decimal(str(loan.principal_amount or 0))" in router
    assert "rounding=ROUND_CEILING" in router
    assert 'provider_request["TotalInstallment"] = deduction_period' in router
    assert "expected_installments=deduction_period" in router
