from decimal import Decimal
from pathlib import Path

import pytest

from payment_engine.allocation_shadow import InstallmentSnapshot, compare_allocation


def test_shadow_matches_oldest_first_allocation():
    result = compare_allocation(
        received=Decimal("600"),
        before=(
            InstallmentSnapshot("a", Decimal("1000"), Decimal("500")),
            InstallmentSnapshot("b", Decimal("1000"), Decimal("0")),
        ),
        actual=(("a", Decimal("500")), ("b", Decimal("100"))),
    )
    assert result.result == "match"
    assert result.unapplied_amount == Decimal("0.00")


def test_shadow_reports_divergence_without_posting():
    result = compare_allocation(
        received=Decimal("600"),
        before=(
            InstallmentSnapshot("a", Decimal("1000"), Decimal("500")),
            InstallmentSnapshot("b", Decimal("1000"), Decimal("0")),
        ),
        actual=(("a", Decimal("400")), ("b", Decimal("200"))),
    )
    assert result.result == "divergence"


def test_excess_payment_explicit_in_shadow():
    result = compare_allocation(
        received=Decimal("1500"),
        before=(InstallmentSnapshot("a", Decimal("1000"), Decimal("0")),),
        actual=(("a", Decimal("1000")),),
    )
    assert result.result == "match"
    assert result.unapplied_amount == Decimal("500.00")


def test_invalid_ledger_snapshot_fails_closed():
    with pytest.raises(ValueError, match="Invalid"):
        compare_allocation(
            received=Decimal("100"),
            before=(InstallmentSnapshot("a", Decimal("100"), Decimal("120")),),
            actual=(),
        )


def test_shadow_is_optional_and_before_live_balance_update():
    source = (Path(__file__).resolve().parents[1] / "services" / "loan_service.py").read_text()
    start = source.index("def allocate_repayment(")
    end = source.index("def finalize_loan_payment(", start)
    portion = source[start:end]
    assert 'os.getenv("LOANHUB_PAYMENT_ENGINE_ALLOCATION_SHADOW", "")' in portion
    assert portion.index("compare_allocation(") < portion.index("loan.amount_paid = money(")
    assert "logging.getLogger(__name__).exception(" in portion


def test_shadow_module_never_writes():
    source = (Path(__file__).resolve().parents[1] / "payment_engine" / "allocation_shadow.py").read_text()
    for forbidden in ("db.commit(", "db.flush(", "db.add(", "db.delete("):
        assert forbidden not in source
