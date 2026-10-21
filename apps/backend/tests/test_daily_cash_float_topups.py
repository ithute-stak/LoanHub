"""Cash top-ups must be authorization-gated, auditable and ledger-backed."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/accounting.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/finance-desk/page.tsx").read_text()
TOPUP = API.split('class DailyCashFloatTopUp(BaseModel):',1)[1].split('class DailyCashClose(BaseModel):',1)[0]

def test_topup_authorization_and_financial_posting():
    assert 'require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})' in TOPUP
    assert 'record.status != "open"' in TOPUP
    assert 'record.branch_id != context.branch_id' in TOPUP
    assert 'reference_type="daily_cash_float"' in TOPUP
    assert 'debit_code="1000"' in TOPUP
    assert '"owner_float": "3000", "bank_withdrawal": "1010", "other": "2990"' in TOPUP
    assert '"float_topups"' in TOPUP

def test_float_is_accounted_for_in_journal_cash_movement_only_once():
    assert 'AccountingAccount.code == "1000"' in API
    assert '"float_topups": cash_data.get("float_topups", [])' in API
    assert 'Number(cashSession.counted_opening) + (cashSession.float_topups ?? []).reduce' in UI
    assert 'api.post(`/accounting/daily-cash/${cashSession.id}/top-up`' in UI

def test_responsive_sections_are_separated():
    for value in ('cash', 'expenses', 'payments', 'legacy', 'reports'):
        assert f'TabsTrigger value="{value}"' in UI
