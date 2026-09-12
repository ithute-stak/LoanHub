from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]
FRONTEND_APP = REPO_ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company"


def test_clients_surface_exposes_borrower_command_centre():
    layout = (FRONTEND_APP / "clients" / "layout.tsx").read_text(encoding="utf-8")
    directory = (FRONTEND_APP / "borrowers" / "page.tsx").read_text(encoding="utf-8")
    assert 'href="/company/borrowers"' in layout
    assert "Borrower command centre" in layout
    assert "listCompanyClients({ limit: 1000 })" in directory
    assert "href={`/company/borrowers/${client.borrower_id}`}" in directory


def test_borrower_workspace_layout_keeps_directory_visible():
    layout = (FRONTEND_APP / "borrowers" / "layout.tsx").read_text(encoding="utf-8")
    assert 'href="/company/clients"' in layout
    assert 'href="/company/borrowers"' in layout
    assert "calls, recordings" in layout


def test_collections_surface_exposes_lelefa_managed_collections():
    layout = (FRONTEND_APP / "collections" / "layout.tsx").read_text(encoding="utf-8")
    page = (FRONTEND_APP / "collections" / "lelefa" / "page.tsx").read_text(encoding="utf-8")
    assert 'href: "/company/collections/lelefa"' in layout
    assert "Lelefa managed collections" in layout
    assert "Select clients" in page
    assert "Switch & rules" in page
    assert "Requests & offers" in page
