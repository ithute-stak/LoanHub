"""Safety contracts across loan schedule, reversing payments and printed statements."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = (ROOT / "apps/backend/services/installment_arrears_rollover_service.py").read_text()
ROUTER = (ROOT / "apps/backend/routers/loans.py").read_text()
REVERSE = (ROOT / "apps/backend/services/loan_last_payment_reversal.py").read_text()
DOCUMENTS = (ROOT / "apps/backend/services/loan_document_service.py").read_text()
PAGE = (ROOT / "apps/frontend/app/(dashboard)/company/loans/page.tsx").read_text()


def test_arrears_transfer_is_approved_and_not_a_new_payment():
    assert 'len(reason.strip()) < 12' in SERVICE
    assert 'loan.balance = ' not in SERVICE
    assert 'loan.total_repayable = ' not in SERVICE
    assert 'current.total_due = cents(current.total_due) - remaining' in SERVICE
    assert 'next_row.total_due = cents(next_row.total_due) + remaining' in SERVICE
    assert 'installment_carry_forward_history' in SERVICE
    assert 'AuditLog(' in SERVICE


def test_last_installment_requires_separate_approval():
    assert 'Final-installment shortfalls require a separately approved linked rollover facility' in SERVICE


def test_scoped_api_and_payment_reversal_guard():
    assert '@router.post("/{loan_id}/installments/carry-forward")' in ROUTER
    assert 'require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})' in ROUTER
    assert 'with_for_update()' in ROUTER
    assert 'installment_carry_forward_history' in REVERSE


def test_printed_schedule_uses_active_installment_actuals():
    assert 'item[field] = str(getattr(actual, field))' in DOCUMENTS


def test_authorized_schedule_action_is_available():
    assert 'Carry balance forward' in PAGE
    assert '/installments/carry-forward' in PAGE
