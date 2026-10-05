"""Concurrency contracts inspired by DBMS transaction-management principles."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_disbursement_locks_loan_before_mutable_status_check() -> None:
    service = _read(ROOT / "services/loan_service.py")
    start = service.index("def disburse_cash_loan(")
    block = service[start:start + 4200]

    lock_pos = block.index(".with_for_update()")
    status_pos = block.index("if loan.status != LoanStatus.APPROVED:")
    payment_pos = block.index("PaymentTransaction(")
    assert lock_pos < status_pos < payment_pos
    assert "Serialize every payout attempt for this loan" in block


def test_credit_bureau_billing_mutations_lock_financial_rows() -> None:
    service = _read(ROOT / "services/credit_bureau_payg_service.py")

    waive = service[service.index("def waive_transaction("):service.index("def create_invoice(")]
    create = service[service.index("def create_invoice("):service.index("def invoice_payload(")]
    paid = service[service.index("def mark_invoice_paid("):service.index("def run_monthly_invoice_cycle(")]

    assert ".with_for_update()" in waive
    assert ".with_for_update()" in create
    assert ".with_for_update()" in paid
    assert ".order_by(PlatformCreditBureauTransaction.id.asc())" in paid


def test_cdas_billing_mutations_lock_financial_rows_in_deterministic_order() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")

    waive = service[service.index("def waive_transaction("):service.index("def refund_transaction(")]
    refund = service[service.index("def refund_transaction("):service.index("def transaction_payload(")]
    create = service[service.index("def create_invoice("):service.index("def invoice_payload(")]
    paid = service[service.index("def mark_invoice_paid("):service.index("def run_monthly_invoice_cycle(")]

    assert ".with_for_update()" in waive
    assert ".with_for_update()" in refund
    assert ".with_for_update()" in create
    assert ".with_for_update()" in paid
    assert ".order_by(PlatformCdasTransaction.id.asc())" in paid
