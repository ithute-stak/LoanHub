from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_document_pdf_branding_resolves_document_studio_company_logo() -> None:
    text = (ROOT / "services" / "document_branding_service.py").read_text(encoding="utf-8")
    assert "WorkspaceDocumentAsset" in text
    assert "def resolve_company_document_logo" in text
    assert "workspace = _latest_workspace_logo_asset(db, company_id)" in text
    assert 'source="workspace_default"' in text


def test_contract_service_has_two_real_style_profiles() -> None:
    text = (ROOT / "services" / "contract_service.py").read_text(encoding="utf-8")
    assert 'CONTRACT_STYLE_STANDARD = "loanhub_standard"' in text
    assert 'CONTRACT_STYLE_FILIZWA = "filizwa_style"' in text
    assert "def _filizwa_styles" in text
    assert 'terms["contract_template_style"]' in text
    assert "template_style: str | None = None" in text
    assert "Contract style cannot change after either party has signed" in text


def test_router_passes_contract_style_to_service() -> None:
    text = (ROOT / "routers" / "origination.py").read_text(encoding="utf-8")
    assert "template_style=payload.template_style" in text
    assert 'data["template_style"]' in text


def test_frontend_document_centre_has_style_selector() -> None:
    frontend = ROOT.parent / "frontend"
    page = (frontend / "app" / "(dashboard)" / "company" / "loans" / "page.tsx").read_text(encoding="utf-8")
    api = (frontend / "api" / "origination.ts").read_text(encoding="utf-8")
    assert "Contract PDF style" in page
    assert "regenerateDocumentCentreContract" in page
    assert "Apply style" in page
    assert "template_style: templateStyle" in api
