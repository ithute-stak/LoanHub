"""Phase 2 unified CDAS registration assessment frontend wiring."""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/cdas/page.tsx"


def test_registration_assessment_connects_to_backend_and_displays_provider_data():
    source = FRONTEND.read_text(encoding="utf-8")
    assert '"/cdas/employees/registration-context"' in source
    assert "existing_deduction_count" in source
    assert "existing_deductions" in source
    assert "registrationAssessment.affordability" in source
    assert "registrationAssessment.payroll_profile_found" in source
    assert "registrationAssessment.can_register" in source
    assert "registrationAssessment.matched_loan" in source
    assert "registrationAssessment.reason" in source
    assert 'This does not register a deduction.' in source


def test_assessment_limited_to_company_management_and_resets_on_employee_change():
    source = FRONTEND.read_text(encoding="utf-8")
    assert "if (!normalizedEmployeeNo || busy || !canManage) return;" in source
    assert "{canManage && (" in source
    assert "setRegistrationAssessment(null);" in source
