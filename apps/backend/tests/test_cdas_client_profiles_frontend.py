from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CDAS_ROOT = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking"
LAYOUT = CDAS_ROOT / "layout.tsx"
CLIENTS_PAGE = CDAS_ROOT / "clients" / "page.tsx"
CLIENTS = CDAS_ROOT / "CdasClientProfiles.tsx"
API = ROOT / "frontend" / "api" / "cdasBooking.ts"


def test_cdas_workspace_exposes_client_profiles_navigation_and_route():
    layout = LAYOUT.read_text(encoding="utf-8")
    page = CLIENTS_PAGE.read_text(encoding="utf-8")

    assert "/company/cdas-booking/clients" in layout
    assert "Client Profiles" in layout
    assert "CdasClientProfiles" in page


def test_client_profile_view_contains_current_deductions_and_full_history():
    source = CLIENTS.read_text(encoding="utf-8")

    assert "CDAS Client Profiles" in source
    assert "Current deductions" in source
    assert "Analysis history" in source
    assert "Booking history" in source
    assert "Open profile" in source
    assert "Employer" in source
    assert "Available capacity" in source


def test_client_profiles_use_tenant_scoped_cdas_api_routes():
    source = API.read_text(encoding="utf-8")

    assert '"/cdas-booking/clients"' in source
    assert "/cdas-booking/clients/${encodeURIComponent(clientKey)}" in source
