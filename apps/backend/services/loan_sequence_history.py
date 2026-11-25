"""Read-only projection of recorded loan field changes."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

_MONEY = frozenset({"principal_amount", "processing_fee", "total_repayable",
                    "installment_amount", "amount_paid", "balance",
                    "top_up_settlement_amount", "top_up_cash_amount"})
_NUMERIC = _MONEY | {"interest_rate"}
_INTEGER = frozenset({"repayment_period", "preferred_payment_day", "renewal_cycle_count"})
_DATE = frozenset({"first_payment_due", "maturity_date", "original_maturity_date"})
_STATUS = frozenset({"status", "repayment_type"})
_FIELDS = _NUMERIC | _INTEGER | _DATE | _STATUS


def _safe_value(field, value):
    if value is None:
        return True, None
    if field in _NUMERIC:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            return False, None
        try:
            raw = str(value)
            if not re.fullmatch(r"-?\d{1,15}(\.\d{1,6})?", raw):
                return False, None
            number = Decimal(raw)
            return True, format(number, "f")
        except (InvalidOperation, ValueError):
            return False, None
    if field in _INTEGER:
        return (True, value) if type(value) is int and 0 <= value <= 100000 else (False, None)
    if field in _DATE:
        if not isinstance(value, str):
            return False, None
        try:
            return True, date.fromisoformat(value).isoformat()
        except ValueError:
            return False, None
    if field in _STATUS and isinstance(value, str) and re.fullmatch(r"[A-Za-z_]{1,40}", value):
        return True, value
    return False, None


def recorded_loan_changes(before_data, after_data):
    """Do not expose arbitrary audit JSON or invent absent historical values."""
    before = before_data if isinstance(before_data, dict) else {}
    after = after_data if isinstance(after_data, dict) else {}
    changes = []
    for field in sorted(_FIELDS & (before.keys() | after.keys())):
        old_present = field in before
        new_present = field in after
        old_valid, old = _safe_value(field, before.get(field))
        new_valid, new = _safe_value(field, after.get(field))
        if not old_valid or not new_valid:
            continue
        if old_present and new_present:
            if old == new or (field in _NUMERIC and old is not None and new is not None and Decimal(old) == Decimal(new)):
                continue
        changes.append({"field": field, "before_recorded": old_present,
                        "after_recorded": new_present, "before": old, "after": new})
    return changes


def recorded_balance_impact(before_data, after_data, status):
    """Compare recorded loan-row balance snapshots, not cash or ledger postings."""
    unavailable = {"evidence": "not_recorded", "before": None, "after": None, "delta": None}
    if status != "success":
        return {**unavailable, "evidence": "not_confirmed"}
    if not isinstance(before_data, dict) or not isinstance(after_data, dict):
        return unavailable
    amounts = []
    for snapshot in (before_data, after_data):
        valid, value = _safe_value("balance", snapshot.get("balance"))
        if not valid or value is None:
            return unavailable
        number = Decimal(value)
        if number != number.quantize(Decimal("0.01")) or abs(number) >= Decimal("10000000000000"):
            return unavailable
        amounts.append(number)
    before, after = amounts
    return {"evidence": "recorded_loan_balance",
            "before": format(before, ".2f"), "after": format(after, ".2f"),
            "delta": format(after - before, ".2f")}
