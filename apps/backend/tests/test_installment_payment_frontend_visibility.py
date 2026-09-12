from pathlib import Path


def test_repayment_schedule_keeps_pay_installment_visible_for_open_rows():
    page = Path(__file__).parents[2] / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "page.tsx"
    text = page.read_text(encoding="utf-8")

    assert "showPaymentAction = !lockedInstallment" in text
    assert "disabled={!canPayNow}" in text
    assert "Pay installment" in text
    assert "loan must be active or defaulted" in text
