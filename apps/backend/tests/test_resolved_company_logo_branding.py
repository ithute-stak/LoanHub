from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"


def test_branding_payload_uses_unified_resolved_company_logo_endpoint() -> None:
    source = (BACKEND_ROOT / "services" / "document_branding_service.py").read_text(encoding="utf-8")

    assert "def resolve_company_document_logo" in source
    assert 'source="managed_right"' in source
    assert 'source="workspace_default"' in source
    assert 'source="managed_left"' in source
    assert 'f"/companies/{company.id}/branding/logo/content"' in source


def test_company_logo_content_route_is_tenant_protected() -> None:
    source = (BACKEND_ROOT / "routers" / "company.py").read_text(encoding="utf-8")

    assert '@router.get("/{company_id}/branding/logo/content")' in source
    assert "Cross-company access is not allowed" in source
    assert "resolve_company_document_logo" in source
    assert '"X-LoanHub-Logo-Source": logo.source' in source


def test_borrower_report_uses_three_part_company_and_system_header() -> None:
    source = (FRONTEND_ROOT / "lib" / "borrower-history-report.ts").read_text(encoding="utf-8")

    assert "brand.companyLogoDataUrl" in source
    assert 'grid-template-columns:190px minmax(0,1fr) 118px' in source
    assert 'class="system-brand"' in source
    assert 'class="system-logo"' in source
    assert "loanhub-horizontal-logo.png" in source
    assert 'class="company-brand"' in source
    assert 'class="company-logo-wrap"' in source
    assert "width:108px" in source
    assert "loanhub-app-icon.png" in source
    assert "generated-by" in source
    assert "Promise.all(images.map" in source
