"""Pure, fail-closed document intelligence rules.

No file uploads, OCR, database writes or loan decisions occur here. The module
normalizes parsed data supplied by future bank and government payslip adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
import calendar
import re
from typing import Mapping, Sequence


class DocumentKind(str, Enum):
    BANK_STATEMENT = "bank_statement"
    GOVERNMENT_PAYSLIP = "government_payslip"
    UNKNOWN = "unknown"


class StampStatus(str, Enum):
    VALID_DATE = "valid_date"
    EXPIRED = "expired"
    FUTURE_DATE = "future_date"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


def orientation_candidates() -> tuple[int, ...]:
    """Right-angle OCR candidates; fine-angle deskew is a separate preprocessing step."""
    return (0, 90, 180, 270)


def classify_document(text: str) -> DocumentKind:
    """A conservative text hint, not document authenticity verification."""
    normalized = re.sub(r"\s+", " ", text).casefold()
    if "staff payslip" in normalized and ("deductions" in normalized or "net pay" in normalized):
        return DocumentKind.GOVERNMENT_PAYSLIP
    if ("opening balance" in normalized and "closing balance" in normalized
            and ("transaction" in normalized or "debit" in normalized)):
        return DocumentKind.BANK_STATEMENT
    return DocumentKind.UNKNOWN


def subtract_calendar_months(value: date, months: int) -> date:
    """Subtract whole calendar months, clamping short-month days."""
    if months < 0:
        raise ValueError("months must be non-negative")
    index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(index, 12)
    month = zero_based_month + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class StampAssessment:
    status: StampStatus
    assessed_at: date
    earliest_accepted: date
    stamp_date: date | None

    @property
    def passes_date_policy(self) -> bool:
        return self.status == StampStatus.VALID_DATE


def assess_stamp_dates(
    detected_dates: Sequence[date], *,
    assessed_at: date,
    maximum_age_months: int = 3,
) -> StampAssessment:
    """Never infer a date from an unreadable stamp; conflicts require review.

    detected_dates must contain only dates confidently assigned to a *stamp*,
    not unrelated dates such as DOB, payroll period, or employment date.
    """
    minimum = subtract_calendar_months(assessed_at, maximum_age_months)
    unique_dates = set(detected_dates)
    if not unique_dates:
        return StampAssessment(StampStatus.MISSING, assessed_at, minimum, None)
    if len(unique_dates) != 1:
        return StampAssessment(StampStatus.AMBIGUOUS, assessed_at, minimum, None)
    stamp_date = next(iter(unique_dates))
    status = (
        StampStatus.FUTURE_DATE if stamp_date > assessed_at
        else StampStatus.EXPIRED if stamp_date < minimum
        else StampStatus.VALID_DATE
    )
    return StampAssessment(status, assessed_at, minimum, stamp_date)


def money(value: str | int | Decimal) -> Decimal:
    """Return exact LSL cents and reject invalid, negative, or overprecision values."""
    if isinstance(value, bool):
        raise ValueError("boolean is not money")
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid monetary value") from exc
    if not parsed.is_finite() or parsed < 0 or parsed.as_tuple().exponent < -2:
        raise ValueError("money must be finite, non-negative and have at most two decimals")
    return parsed.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class PayslipTotals:
    total_earnings: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    is_reconciled: bool


def validate_payslip_totals(
    earnings: Sequence[str | int | Decimal],
    deductions: Sequence[str | int | Decimal],
    *,
    printed_earnings: str | int | Decimal,
    printed_deductions: str | int | Decimal,
    printed_net_pay: str | int | Decimal,
) -> PayslipTotals:
    """Arithmetic-only check; no claim that OCR or issuer authenticity is verified."""
    gross = sum((money(value) for value in earnings), Decimal("0.00"))
    deducted = sum((money(value) for value in deductions), Decimal("0.00"))
    net = gross - deducted
    reconciled = (
        gross == money(printed_earnings)
        and deducted == money(printed_deductions)
        and net == money(printed_net_pay)
        and net >= 0
    )
    return PayslipTotals(gross, deducted, net, reconciled)


@dataclass(frozen=True)
class BankTransaction:
    debit: Decimal
    credit: Decimal
    resulting_balance: Decimal


def validate_statement_balances(
    opening_balance: str | int | Decimal,
    closing_balance: str | int | Decimal,
    transactions: Sequence[BankTransaction],
) -> bool:
    """Verify every running balance, not just the statement closing balance."""
    balance = money(opening_balance)
    for row in transactions:
        if row.debit < 0 or row.credit < 0 or row.debit and row.credit:
            return False
        balance = balance - row.debit + row.credit
        if balance != row.resulting_balance:
            return False
    return balance == money(closing_balance)
