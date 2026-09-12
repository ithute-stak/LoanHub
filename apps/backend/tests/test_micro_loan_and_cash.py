from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus, PaymentProvider
from services.loan_service import calculate_micro_loan_totals, preview_cash_repayment
from services.payment_service import initiate_payment


def test_micro_loan_example_matches_owner_method():
    monthly, total, details = calculate_micro_loan_totals(
        Decimal("1000"), Decimal("20"), 3, Decimal("0")
    )
    assert details["components"] == ["600.00", "360.00", "432.00"]
    assert total == Decimal("1392.00")
    assert monthly == Decimal("464.00")
    assert sum(map(Decimal, details["schedule_amounts"])) == total


def test_micro_loan_rounding_keeps_schedule_balanced():
    monthly, total, details = calculate_micro_loan_totals(
        Decimal("1250.35"), Decimal("17.5"), 7, Decimal("50")
    )
    schedule = list(map(Decimal, details["schedule_amounts"]))
    assert len(schedule) == 7
    assert sum(schedule) == total
    assert schedule[0] == monthly


def _loan():
    installments = [
        SimpleNamespace(
            installment_number=1,
            due_date=date(2026, 8, 20),
            total_due=Decimal("464.00"),
            paid_amount=Decimal("0.00"),
            status=InstallmentStatus.PENDING,
        ),
        SimpleNamespace(
            installment_number=2,
            due_date=date(2026, 9, 20),
            total_due=Decimal("464.00"),
            paid_amount=Decimal("0.00"),
            status=InstallmentStatus.PENDING,
        ),
        SimpleNamespace(
            installment_number=3,
            due_date=date(2026, 10, 20),
            total_due=Decimal("464.00"),
            paid_amount=Decimal("0.00"),
            status=InstallmentStatus.PENDING,
        ),
    ]
    person = SimpleNamespace(first_name="Kabelo", middle_name=None, last_name="Mokoena")
    borrower = SimpleNamespace(user=SimpleNamespace(person=person))
    return SimpleNamespace(
        id=uuid4(),
        loan_reference="LB-20260720-123456-TEST-COMPANY",
        status=LoanStatus.ACTIVE,
        installments=installments,
        balance=Decimal("1392.00"),
        installment_amount=Decimal("464.00"),
        borrower=borrower,
    )


def test_partial_cash_payment_shows_remaining_installment():
    result = preview_cash_repayment(
        _loan(), amount_tendered=Decimal("300"), overpayment_action="carry_forward"
    )
    assert result["amount_applied"] == Decimal("300.00")
    assert result["installment_outstanding_after"] == Decimal("164.00")
    assert result["change_amount"] == Decimal("0.00")


def test_overpayment_can_return_change():
    result = preview_cash_repayment(
        _loan(), amount_tendered=Decimal("600"), overpayment_action="give_change"
    )
    assert result["amount_applied"] == Decimal("464.00")
    assert result["change_amount"] == Decimal("136.00")
    assert result["forward_amount"] == Decimal("0.00")


def test_overpayment_can_pay_ahead():
    result = preview_cash_repayment(
        _loan(), amount_tendered=Decimal("600"), overpayment_action="carry_forward"
    )
    assert result["amount_applied"] == Decimal("600.00")
    assert result["change_amount"] == Decimal("0.00")
    assert result["forward_amount"] == Decimal("136.00")
    assert result["installments_fully_covered"] == 1


def test_non_cash_payment_without_proof_is_rejected():
    with pytest.raises(HTTPException) as caught:
        initiate_payment(
            SimpleNamespace(),
            provider=PaymentProvider.MPESA,
            purpose=SimpleNamespace(),
            amount=Decimal("1"),
            idempotency_key="test",
            initiated_by_user_id=None,
        )
    assert caught.value.status_code == 422


def test_micro_loan_single_month_applies_rate_once():
    monthly, total, details = calculate_micro_loan_totals(
        Decimal("1000"), Decimal("20"), 1, Decimal("0")
    )
    assert details["components"] == ["1200.00"]
    assert total == Decimal("1200.00")
    assert monthly == Decimal("1200.00")


def test_advance_payment_never_applies_more_than_loan_balance():
    result = preview_cash_repayment(
        _loan(), amount_tendered=Decimal("2000"), overpayment_action="carry_forward"
    )
    assert result["amount_applied"] == Decimal("1392.00")
    assert result["change_amount"] == Decimal("608.00")
    assert result["forward_amount"] == Decimal("928.00")
    assert result["payment_completes_loan"] is True


def test_generated_loan_reference_is_compact_and_uses_company_initials(monkeypatch):
    from services import loan_service

    class EmptyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class EmptyDb:
        def query(self, *_args, **_kwargs):
            return EmptyQuery()

    characters = iter("8F3K29")
    monkeypatch.setattr(loan_service.secrets, "choice", lambda _alphabet: next(characters))

    reference = loan_service.generate_loan_reference(
        EmptyDb(),
        "Batlokoa Financial Services",
    )

    assert reference == "LBBFS8F3K29"
    assert len(reference) == 11
    assert reference.isalnum()
    assert reference == reference.upper()
    assert "-" not in reference


def test_generated_loan_reference_retries_a_collision(monkeypatch):
    from services import loan_service

    class CollisionQuery:
        calls = 0

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            self.calls += 1
            return object() if self.calls == 1 else None

    class CollisionDb:
        query_instance = CollisionQuery()

        def query(self, *_args, **_kwargs):
            return self.query_instance

    characters = iter("AAAAAABBBBBB")
    monkeypatch.setattr(loan_service.secrets, "choice", lambda _alphabet: next(characters))

    reference = loan_service.generate_loan_reference(
        CollisionDb(),
        "Maseru Community Finance",
    )

    assert reference == "LBMCFBBBBBB"
    assert CollisionDb.query_instance.calls == 2


def test_assisted_account_opening_fee_is_company_cash_out():
    from database.models.enums import PaymentPurpose
    from services.payment_service import OUTBOUND_PURPOSES

    assert PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE in OUTBOUND_PURPOSES


def test_assisted_opening_fee_has_company_and_platform_accounts():
    from services.accounting_service import COMPANY_CHART, PLATFORM_CHART

    assert any(code == "6400" for code, *_ in COMPANY_CHART)
    assert any(code == "4400" for code, *_ in PLATFORM_CHART)
