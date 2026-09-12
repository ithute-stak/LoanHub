from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from database.schemas.company_website import CompanyWebsiteUpdate
from routers.company_websites import _slug, router as company_website_router
from routers.workspace_spreadsheets import DATABASE_TEMPLATES, router as spreadsheet_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"


def test_company_public_code_slug_is_url_safe_and_stable() -> None:
    assert _slug("Batlokoa Financial Services Ltd") == "batlokoa-financial-services-ltd"
    assert _slug("  M&M / Loans!!! ") == "m-m-loans"


def test_company_website_update_accepts_only_supported_templates() -> None:
    assert CompanyWebsiteUpdate(template_key="trust_community").template_key == "trust_community"
    assert CompanyWebsiteUpdate(template_key="modern_finance").template_key == "modern_finance"
    with pytest.raises(ValidationError):
        CompanyWebsiteUpdate(template_key="unknown")


def test_company_website_colour_validation_rejects_non_hex_values() -> None:
    assert CompanyWebsiteUpdate(primary_color="#0f4c81").primary_color == "#0F4C81"
    with pytest.raises(ValidationError):
        CompanyWebsiteUpdate(primary_color="blue")


def test_company_website_router_exposes_builder_products_and_public_site() -> None:
    paths = {route.path for route in company_website_router.routes}
    assert "/company-websites/mine" in paths
    assert "/company-websites/start" in paths
    assert "/company-websites/loan-products" in paths
    assert "/company-websites/publish" in paths
    assert "/company-websites/public/{public_code}" in paths


def test_spreadsheet_pro_exposes_database_refresh_route() -> None:
    paths = {route.path for route in spreadsheet_router.routes}
    assert "/workspace-spreadsheets/{document_id}/refresh-loanhub-data" in paths
    assert DATABASE_TEMPLATES == {"loan_portfolio", "cashbook", "collections"}


def test_company_website_migration_follows_current_head() -> None:
    migration = (BACKEND_ROOT / "alembic" / "versions" / "b1q5s7u9v021_company_public_website_builder.py").read_text()
    assert 'revision: str = "b1q5s7u9v021"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "a0p4r6s8t910"' in migration
    assert '"company_website_profiles"' in migration
    assert '"public_code"' in migration


def test_frontend_has_independent_spreadsheet_fullscreen_and_mobile_document_gate() -> None:
    spreadsheet = (FRONTEND_ROOT / "components" / "documents" / "spreadsheet-editor.tsx").read_text()
    workspace = (FRONTEND_ROOT / "components" / "documents" / "workspace-item-editor.tsx").read_text()
    office_css = (FRONTEND_ROOT / "app" / "office-workspace.css").read_text()

    assert 'data-spreadsheet-fullscreen={fullscreen ? "true" : "false"}' in spreadsheet
    assert 'onClick={() => setFullscreen((value) => !value)}' in spreadsheet
    assert 'className="hidden md:block"' in workspace
    assert 'className="flex min-h-[70dvh] items-center justify-center p-5 md:hidden"' in workspace
    assert 'html[data-loanhub-workspace="fullscreen"] [data-spreadsheet-fullscreen="false"]' in office_css


def test_public_company_site_uses_real_api_products_not_demo_product_names() -> None:
    builder = (FRONTEND_ROOT / "components" / "company" / "company-website-builder.tsx").read_text()
    public_site = (FRONTEND_ROOT / "app" / "[companyCode]" / "page.tsx").read_text()

    assert "getCompanyWebsiteLoanProducts" in builder
    assert "visibleProducts.map" in builder
    assert "site.loan_products.map" in public_site
    assert "Short-term loan" not in builder
    assert "Personal loan" not in builder
    assert "Business loan" not in builder
