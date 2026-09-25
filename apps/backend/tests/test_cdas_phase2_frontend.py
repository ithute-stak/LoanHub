from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CDAS_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "page.tsx"
SETTINGS = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "settings" / "_components" / "company-cdas-settings.tsx"
LEGACY_ROUTES = [
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "management-dashboard" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "verify-employee" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "lifecycle" / "page.tsx",
]


def test_phase2_employee_verification_is_manual_and_uses_clean_api_route() -> None:
    source = CDAS_PAGE.read_text(encoding="utf-8")

    assert 'api.post<EmployeeLookupResponse>("/cdas/employees/verify"' in source
    assert "onSubmit={verifyEmployee}" in source
    assert 'employee_no: normalized' in source
    assert "useEffect" not in source
    assert "Manual verification only" in source
    assert "400 requests per day per API user" in source


def test_phase2_ui_exposes_only_documented_employee_detail_fields() -> None:
    source = CDAS_PAGE.read_text(encoding="utf-8")

    for field in (
        "EmployeeNo",
        "Name",
        "Surname",
        "DOB",
        "Department",
        "JoiningDate",
        "TerminationDate",
    ):
        assert field in source

    for future_operation in (
        "/check-affordability",
        "/view-all-deduction",
        "/view-deduction",
        "/add-update-deduction",
        "/modify-active-deduction",
        "/settled-deduction",
        "/get_document",
    ):
        assert future_operation not in source


def test_settings_describes_phase2_without_enabling_future_cdas_operations() -> None:
    source = SETTINGS.read_text(encoding="utf-8")

    assert "Phase 2 adds only deliberate employee verification" in source
    assert "affordability, deduction, document, booking, intelligence and background CDAS operations remain disabled" in source


def test_retired_cdas_booking_routes_are_redirects_only() -> None:
    for route in LEGACY_ROUTES:
        source = route.read_text(encoding="utf-8")
        assert 'redirect("/company/cdas")' in source
        assert "api." not in source
