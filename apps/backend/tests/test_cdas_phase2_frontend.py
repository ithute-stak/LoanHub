from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CDAS_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "page.tsx"
LEGACY_ROUTES = [
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "management-dashboard" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "verify-employee" / "page.tsx",
    ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "lifecycle" / "page.tsx",
]


def test_cdas_read_workspace_is_manual_and_uses_clean_api_routes() -> None:
    source = CDAS_PAGE.read_text(encoding="utf-8")

    for route in (
        "/cdas/employees/verify",
        "/cdas/employees/affordability",
        "/cdas/deductions/all",
        "/cdas/deductions/own",
        "/cdas/deductions/active-approved",
    ):
        assert route in source

    assert "onSubmit={verifyEmployee}" in source
    assert "useEffect" not in source
    assert "Manual requests only" in source
    assert "400 requests per day per API user" in source


def test_employee_details_remain_limited_to_documented_fields() -> None:
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


def test_read_workspace_separates_state_changing_actions() -> None:
    source = CDAS_PAGE.read_text(encoding="utf-8")

    for provider_write_path in (
        "/add-update-deduction",
        "/modify-active-deduction",
        "/settled-deduction",
        "/get_document",
    ):
        assert provider_write_path not in source

    assert "/company/cdas/operations" in source
    assert "/company/cdas/documents" in source
    assert "COMPANY_MANAGEMENT_ROLES" in source
    assert "explicit confirmation and audit logging" in source


def test_retired_cdas_booking_routes_are_redirects_only() -> None:
    for route in LEGACY_ROUTES:
        source = route.read_text(encoding="utf-8")
        assert 'redirect("/company/cdas")' in source
        assert "api." not in source
