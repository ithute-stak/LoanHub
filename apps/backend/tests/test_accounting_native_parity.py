from decimal import Decimal

import pytest

from services.accounting_native_parity import compare_trial_balance, reference_trial_balance


ROWS = [
    (20, Decimal("0.00"), Decimal("12.50")),
    (10, Decimal("12.50"), Decimal("0.00")),
]


def test_reference_sorted_accounts():
    assert reference_trial_balance(ROWS) == (
        "1250|1250\n10|1250|0|1250\n20|0|1250|-1250\n"
    )


def test_native_exact_match_is_advisory_only():
    def execute(command, payload):
        assert command == "accounting-trial-balance"
        assert payload == "20|0|1250\n10|1250|0\n"
        return reference_trial_balance(ROWS)

    result = compare_trial_balance(ROWS, execute)
    assert result["native_cpp_matched"] is True
    assert result["authoritative"] is False


def test_native_mismatch_and_error_fail_closed():
    assert compare_trial_balance(ROWS, lambda *_: "wrong")["native_cpp_matched"] is False

    def failed(*_):
        raise RuntimeError("native library unavailable")

    assert compare_trial_balance(ROWS, failed)["native_cpp_matched"] is False


@pytest.mark.parametrize("rows", [
    [(10, Decimal("0.001"), Decimal("0"))],
    [(10, Decimal("-1"), Decimal("0"))],
    [(10, Decimal("1"), Decimal("1"))],
    [(0, Decimal("1"), Decimal("0"))],
    [(10, Decimal("NaN"), Decimal("0"))],
    [(10, Decimal("92233720368547758.08"), Decimal("0"))],
])
def test_rejects_invalid_amounts(rows):
    with pytest.raises((ValueError, OverflowError)):
        reference_trial_balance(rows)
