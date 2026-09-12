from pathlib import Path

import pytest
from pydantic import ValidationError

from routers.loan_settings import CONTRACT_TEMPLATE_STYLES, LoanSettingsUpdate


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_supported_default_contract_templates_are_explicit() -> None:
    assert CONTRACT_TEMPLATE_STYLES == (
        ("loanhub_standard", "LoanHub Standard"),
        ("filizwa_style", "Filizwa Financial"),
    )
    assert LoanSettingsUpdate(
        default_contract_template_style="filizwa_style"
    ).default_contract_template_style == "filizwa_style"


def test_unknown_default_contract_template_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LoanSettingsUpdate(default_contract_template_style="unknown-template")


def test_frontend_contract_generation_resolves_company_default() -> None:
    source = (REPO_ROOT / "apps/frontend/api/origination.ts").read_text(encoding="utf-8")
    assert "loanSettingsApi.getSettings()" in source
    assert "default_contract_template_style" in source
    assert "template_style: resolvedTemplateStyle" in source


def test_company_settings_page_exposes_loan_settings_tab() -> None:
    source = (
        REPO_ROOT
        / "apps/frontend/app/(dashboard)/company/settings/page.tsx"
    ).read_text(encoding="utf-8")
    assert 'value="loan-settings"' in source
    assert "<CompanyLoanSettingsPanel" in source
