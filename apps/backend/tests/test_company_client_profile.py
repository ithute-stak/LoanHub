from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from database.models.enums import InstallmentStatus, LoanStatus, PaymentStatus
from services.borrower_profile_service import build_payment_rating


def installment(*, due_date: date, status: InstallmentStatus, paid_amount: str, paid_at: datetime | None):
    return SimpleNamespace(
        due_date=due_date,
        status=status,
        total_due=Decimal("100.00"),
        paid_amount=Decimal(paid_amount),
        paid_at=paid_at,
    )


def loan(status: LoanStatus):
    return SimpleNamespace(status=status)


def payment(*, completed_at: datetime):
    return SimpleNamespace(
        status=PaymentStatus.SUCCEEDED,
        completed_at=completed_at,
        created_at=completed_at,
    )


def test_profile_routes_are_declared_before_single_account_route():
    from pathlib import Path

    router_file = Path(__file__).parents[1] / "routers" / "company_clients.py"
    source = router_file.read_text(encoding="utf-8")
    profile_path = '"/{account_id}/profile"'
    account_path = '"/{account_id}", response_model=CompanyClientRead'

    assert profile_path in source
    assert '"/{account_id}/profile-image"' in source
    assert '"/{account_id}/documents"' in source
    assert '"/{account_id}/files/{file_id}/content"' in source
    assert account_path in source
    assert source.index(profile_path) < source.index(account_path)


def test_payment_rating_is_not_assigned_before_due_history_exists():
    result = build_payment_rating(
        [
            installment(
                due_date=date(2026, 8, 20),
                status=InstallmentStatus.PENDING,
                paid_amount="0.00",
                paid_at=None,
            )
        ],
        [],
        [],
        today=date(2026, 8, 4),
    )
    assert result.score is None
    assert result.grade == "NR"
    assert result.has_history is False
    assert result.total_due_installments == 0


def test_payment_rating_rewards_consistent_on_time_payment():
    first_paid_at = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
    second_paid_at = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
    result = build_payment_rating(
        [
            installment(
                due_date=date(2026, 6, 30),
                status=InstallmentStatus.PAID,
                paid_amount="100.00",
                paid_at=first_paid_at,
            ),
            installment(
                due_date=date(2026, 7, 31),
                status=InstallmentStatus.PAID,
                paid_amount="100.00",
                paid_at=second_paid_at,
            ),
        ],
        [loan(LoanStatus.COMPLETED)],
        [payment(completed_at=second_paid_at)],
        today=date(2026, 8, 4),
    )
    assert result.score == 100
    assert result.grade == "A"
    assert result.on_time_installments == 2
    assert result.overdue_installments == 0
    assert result.on_time_rate == 1
    assert result.last_payment_at == second_paid_at


def test_payment_rating_penalises_late_overdue_and_defaulted_history():
    result = build_payment_rating(
        [
            installment(
                due_date=date(2026, 6, 30),
                status=InstallmentStatus.PAID,
                paid_amount="100.00",
                paid_at=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
            ),
            installment(
                due_date=date(2026, 7, 31),
                status=InstallmentStatus.OVERDUE,
                paid_amount="20.00",
                paid_at=None,
            ),
        ],
        [loan(LoanStatus.DEFAULTED)],
        [],
        today=date(2026, 8, 4),
    )
    assert result.score is not None
    assert result.score < 50
    assert result.grade == "E"
    assert result.late_installments == 1
    assert result.overdue_installments == 1
    assert result.average_days_late == 5
