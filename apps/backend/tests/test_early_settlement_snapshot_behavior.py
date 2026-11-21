"""Behavioral tests for early-settlement snapshots without database writes."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import InstallmentStatus
from services.early_settlement_service import _installment_snapshot, settlement_due_dates


def _row(number, paid, *, superseded=False):
    return SimpleNamespace(
        id=uuid4(),
        installment_number=number,
        due_date=date(2026, number, 15),
        status=InstallmentStatus.WAIVED if superseded else InstallmentStatus.PAID,
        paid_amount=Decimal(paid),
        paid_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        is_superseded=superseded,
        superseded_at=datetime(2026, 2, 1, tzinfo=timezone.utc) if superseded else None,
    )


def test_snapshot_preserves_cents_on_superseded_waived_rows():
    rows = [_row(1, "642.92"), _row(2, "0.08", superseded=True)]
    snapshot = _installment_snapshot(SimpleNamespace(installments=rows))
    assert snapshot[1]["paid_amount"] == "0.08"
    assert snapshot[1]["status"] == InstallmentStatus.WAIVED.value
    assert snapshot[1]["is_superseded"] is True
    assert snapshot[1]["superseded_at"] is not None
    assert snapshot[1]["paid_at"] is not None


def test_snapshot_preserves_other_legacy_fraction():
    rows = [_row(1, "417.60"), _row(2, "0.40", superseded=True)]
    snapshot = _installment_snapshot(SimpleNamespace(installments=rows))
    assert [entry["paid_amount"] for entry in snapshot] == ["417.60", "0.40"]


def test_settlement_due_dates_excludes_superseded_rows():
    rows = [_row(3, "0.00", superseded=True), _row(2, "0.40"), _row(1, "417.60")]
    loan = SimpleNamespace(installments=rows)
    assert settlement_due_dates(loan) == [date(2026, 1, 15), date(2026, 2, 15)]
