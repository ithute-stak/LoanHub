from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.audit_log import AuditLog
from database.models.enums import InstallmentStatus, LoanStatus, UserRole
from services.installment_service import adjust_installment_due_date


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


def _loan():
    first = SimpleNamespace(
        id=uuid4(),
        installment_number=1,
        due_date=date(2026, 8, 28),
        paid_amount=Decimal("0.00"),
        status=InstallmentStatus.PENDING,
    )
    second = SimpleNamespace(
        id=uuid4(),
        installment_number=2,
        due_date=date(2026, 9, 28),
        paid_amount=Decimal("0.00"),
        status=InstallmentStatus.PENDING,
    )
    third = SimpleNamespace(
        id=uuid4(),
        installment_number=3,
        due_date=date(2026, 10, 28),
        paid_amount=Decimal("0.00"),
        status=InstallmentStatus.PENDING,
    )
    return SimpleNamespace(
        id=uuid4(),
        company_id=uuid4(),
        branch_id=uuid4(),
        loan_reference="LB-TEST-EXTENSION",
        status=LoanStatus.ACTIVE,
        first_payment_due=first.due_date,
        maturity_date=third.due_date,
        is_overdue=False,
        installments=[first, second, third],
    )


def test_due_date_adjustment_changes_date_only_and_writes_audit():
    loan = _loan()
    db = FakeSession()
    first = loan.installments[0]

    adjust_installment_due_date(
        db,
        loan=loan,
        installment_id=first.id,
        new_due_date=date(2026, 9, 10),
        agreement_note="Borrower and lender agreed to a short extension.",
        agreement_reference="AGR-001",
        actor_user_id=uuid4(),
        actor_role=UserRole.LOAN_OFFICER,
    )

    assert first.due_date == date(2026, 9, 10)
    assert loan.first_payment_due == date(2026, 9, 10)
    assert loan.maturity_date == date(2026, 10, 28)
    assert db.commits == 1
    audit = next(value for value in db.added if isinstance(value, AuditLog))
    assert audit.before_data == {"due_date": "2026-08-28"}
    assert audit.after_data == {"due_date": "2026-09-10"}
    assert audit.event_data["financial_amounts_changed"] is False


def test_due_date_adjustment_cannot_shorten_date():
    loan = _loan()
    with pytest.raises(HTTPException) as caught:
        adjust_installment_due_date(
            FakeSession(),
            loan=loan,
            installment_id=loan.installments[0].id,
            new_due_date=date(2026, 8, 20),
            agreement_note="Requested change",
            agreement_reference=None,
            actor_user_id=uuid4(),
            actor_role=UserRole.LOAN_OFFICER,
        )
    assert caught.value.status_code == 422


def test_due_date_adjustment_preserves_schedule_order():
    loan = _loan()
    with pytest.raises(HTTPException) as caught:
        adjust_installment_due_date(
            FakeSession(),
            loan=loan,
            installment_id=loan.installments[0].id,
            new_due_date=date(2026, 9, 28),
            agreement_note="Requested change",
            agreement_reference=None,
            actor_user_id=uuid4(),
            actor_role=UserRole.LOAN_OFFICER,
        )
    assert caught.value.status_code == 409


def test_overdue_installment_becomes_pending_when_extended_into_future(monkeypatch):
    loan = _loan()
    first = loan.installments[0]
    first.status = InstallmentStatus.OVERDUE
    loan.is_overdue = True

    # Use a far-future last installment so the test remains valid regardless of run date.
    loan.installments[1].due_date = date(2035, 9, 28)
    new_date = date(2035, 8, 28)

    adjust_installment_due_date(
        FakeSession(),
        loan=loan,
        installment_id=first.id,
        new_due_date=new_date,
        agreement_note="Formal extension agreed.",
        agreement_reference=None,
        actor_user_id=uuid4(),
        actor_role=UserRole.COMPANY_ADMIN,
    )

    assert first.status == InstallmentStatus.PENDING
    assert loan.is_overdue is False

