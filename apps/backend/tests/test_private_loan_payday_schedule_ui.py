"""Private loan forms should prefill instalments from borrower payday."""
from pathlib import Path
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
CLIENTS = (FRONTEND / "app/(dashboard)/company/clients/page.tsx").read_text()
DATE_HELPER = (FRONTEND / "components/loans/installment-due-date-fields.tsx").read_text()


def test_private_loan_starts_with_next_pay_date_and_can_reset():
    assert "clientPaydaySchedule(client, defaultProduct?.min_term_months ?? 3)" in CLIENTS
    assert "generatePaydayInstallmentDueDates(client.next_salary_pay_date, fallbackDay, count)" in CLIENTS
    assert "Reset to pay dates" in CLIENTS
    assert 'onChange={(dates) => updateLoan("installment_due_dates", dates)}' in CLIENTS


def test_monthly_due_date_generator_clips_month_end():
    assert "export function generatePaydayInstallmentDueDates(" in DATE_HELPER
    assert "nextPayDate > today" in DATE_HELPER
    assert "Math.min(payday, last)" in DATE_HELPER
