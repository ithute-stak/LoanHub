from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from database.models.enums import InstallmentStatus
from routers.legacy_cashout import _calculator_schedule_rows, _create_historical_schedule


def _snapshot() -> dict:
    return {
        "schedule": [
            {
                "installment_number": 1,
                "due_date": "2099-02-01",
                "principal_due": 30,
                "interest_due": 10,
                "fee_due": 0,
                "total_due": 40,
            },
            {
                "installment_number": 2,
                "due_date": "2099-03-01",
                "principal_due": 30,
                "interest_due": 10,
                "fee_due": 0,
                "total_due": 40,
            },
            {
                "installment_number": 3,
                "due_date": "2099-04-01",
                "principal_due": 30,
                "interest_due": 10,
                "fee_due": 0,
                "total_due": 40,
            },
        ],
    }


def test_calculator_schedule_rows_use_the_authoritative_due_amounts():
    rows = _calculator_schedule_rows(
        _snapshot(),
        total_repayable=Decimal("120.00"),
        installment_count=3,
    )

    assert [row["total_due"] for row in rows] == [
        Decimal("40.00"),
        Decimal("40.00"),
        Decimal("40.00"),
    ]
    assert rows[1]["due_date"] == date(2099, 3, 1)


def test_historic_payment_is_allocated_paid_then_partial_then_unpaid():
    class RecordingSession:
        def __init__(self):
            self.rows = []

        def add(self, row):
            self.rows.append(row)

    db = RecordingSession()
    _create_historical_schedule(
        db,
        loan=SimpleNamespace(id="loan-id"),
        loan_date=date(2099, 1, 1),
        repayment_type="monthly",
        total_repayable=Decimal("120.00"),
        principal=Decimal("90.00"),
        amount_paid=Decimal("55.00"),
        installment_count=3,
        calculator_snapshot=_snapshot(),
    )

    assert [row.paid_amount for row in db.rows] == [
        Decimal("40.00"),
        Decimal("15.00"),
        Decimal("0.00"),
    ]
    assert [row.status for row in db.rows] == [
        InstallmentStatus.PAID,
        InstallmentStatus.PARTIALLY_PAID,
        InstallmentStatus.PENDING,
    ]
