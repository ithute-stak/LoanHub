from pathlib import Path

import pytest
from pydantic import ValidationError

from database.schemas.company import LoanCompanyUpdate


ROOT = Path(__file__).resolve().parents[1]


def test_company_shortcode_accepts_only_4_to_12_digits():
    assert LoanCompanyUpdate(mpesa_shortcode=" 123456 ").mpesa_shortcode == "123456"
    assert LoanCompanyUpdate(mpesa_shortcode="").mpesa_shortcode is None
    with pytest.raises(ValidationError):
        LoanCompanyUpdate(mpesa_shortcode="12AB56")
    with pytest.raises(ValidationError):
        LoanCompanyUpdate(mpesa_shortcode="123")


def test_company_model_and_migration_store_only_shortcode_not_mpesa_credentials():
    model = (ROOT / "database/models/company.py").read_text(encoding="utf-8")
    migration = (ROOT / "alembic/versions/b1q5s7t9u022_company_mpesa_shortcode.py").read_text(encoding="utf-8")
    assert "mpesa_shortcode" in model
    assert 'down_revision: Union[str, Sequence[str], None] = "q1c4e7g0h016"' in migration
    for forbidden in ("mpesa_api_key", "mpesa_public_key", "mpesa_origin", "mpesa_session_key"):
        assert forbidden not in model


def test_paybridge_client_loads_shortcode_from_loanhub_database_not_metadata():
    client = (ROOT / "integrations/lelefa_paygate.py").read_text(encoding="utf-8")
    assert "db.get(LoanCompany, company_id)" in client
    assert "company.mpesa_shortcode" in client
    assert "_company_business_shortcode(metadata)" in client
    assert '"business_shortcode": business_shortcode' in client
    assert "This company has not configured its M-Pesa business shortcode" in client


def test_same_shortcode_contract_is_used_for_money_in_money_out_and_checkout():
    client = (ROOT / "integrations/lelefa_paygate.py").read_text(encoding="utf-8")
    payment = client.split("def create_payment_intent", 1)[1].split("def list_payment_methods", 1)[0]
    checkout = client.split("def create_checkout_session", 1)[1].split("def create_payout", 1)[0]
    payout = client.split("def create_payout", 1)[1].split("def create_mandate", 1)[0]
    assert "_company_business_shortcode(metadata)" in payment
    assert "_company_business_shortcode(metadata)" in checkout
    assert "_company_business_shortcode(metadata)" in payout


def test_company_settings_expose_one_simple_mpesa_field():
    ui = (ROOT.parent / "frontend/app/(dashboard)/company/settings/_components/company-settings-form.tsx").read_text(encoding="utf-8")
    assert "M-Pesa business shortcode" in ui
    assert "Used automatically for both money IN (C2B) and money OUT (B2C)" in ui
    assert "No provider credentials are required here" in ui
    # Explanatory copy may mention what PayBridge centrally manages; what must
    # never exist are tenant-editable credential fields or names.
    for forbidden_field in (
        'name="mpesa_api_key"',
        'name="mpesa_public_key"',
        'name="mpesa_origin"',
        'name="mpesa_session_key"',
    ):
        assert forbidden_field not in ui
