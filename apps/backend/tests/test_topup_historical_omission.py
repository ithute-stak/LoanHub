"""Historical top-up omission must preserve actual disbursement timestamps and scope."""
from pathlib import Path

API = (Path(__file__).resolve().parents[1] / "routers/origination.py").read_text()
HISTORICAL = API.split('class HistoricalTopUpOmissionCreate', 1)[1].split('@router.get("/loans/{loan_id}/top-up-settlement-preview")', 1)[0]


def test_historical_topup_is_role_restricted_and_requires_evidence():
    assert 'require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})' in HISTORICAL
    assert 'external_reference: str = Field(min_length=5' in HISTORICAL
    assert 'evidence_reference: str = Field(min_length=5' in HISTORICAL
    assert 'days_ago < 1 or days_ago > 90' in HISTORICAL


def test_historical_topup_uses_existing_underwriting_without_backdating():
    assert 'create_application(payload=payload.application, db=db, context=context)' in HISTORICAL
    assert '"financial_backdating": False' in HISTORICAL
    assert '"requires_historical_settlement_reconciliation": True' in HISTORICAL
    assert 'action="top_up.historical_omission_registered"' in HISTORICAL
    for forbidden in ("disbursed_at =", "approved_at =", "CashTransaction(", "PaymentTransaction("):
        assert forbidden not in HISTORICAL
