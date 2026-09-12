from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Any, Iterable

from database.models.enums import (
    INTEREST_METHOD_LABELS,
    LoanCalculationMethod,
)

MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
TWELVE = Decimal("12")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)



def normalize_interest_method(value: LoanCalculationMethod | str | None) -> LoanCalculationMethod:
    if value is None:
        return LoanCalculationMethod.MICRO_LOAN
    if isinstance(value, LoanCalculationMethod):
        return value
    try:
        return LoanCalculationMethod(str(value).strip().lower())
    except ValueError as exc:
        supported = ", ".join(method.value for method in LoanCalculationMethod)
        raise ValueError(f"Unsupported interest method. Choose one of: {supported}") from exc


def interest_method_label(value: LoanCalculationMethod | str | None) -> str:
    method = normalize_interest_method(value)
    return INTEREST_METHOD_LABELS[method]


def interest_rate_basis(value: LoanCalculationMethod | str | None) -> str:
    method = normalize_interest_method(value)
    if method == LoanCalculationMethod.MICRO_LOAN:
        return "Rate applied per LoanHub Micro Loan calculation cycle"
    if method == LoanCalculationMethod.DAILY_ACCRUAL_REDUCING:
        return "Annual nominal rate divided by 12 and prorated by actual days in each calendar month"
    if method == LoanCalculationMethod.COMPOUND_INTEREST:
        return "Annual nominal rate compounded monthly over the full term"
    if method == LoanCalculationMethod.REDUCING_BALANCE:
        return "Annual nominal rate divided by 12 and charged on the outstanding principal"
    return "Annual nominal rate applied to the original principal for the agreed term"


@dataclass(frozen=True)
class InterestSegment:
    period_start: date
    period_end: date
    days: int
    days_in_month: int
    interest: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "days": self.days,
            "days_in_month": self.days_in_month,
            "interest": str(money(self.interest)),
        }


@dataclass(frozen=True)
class ScheduleRow:
    installment_number: int
    period_start: date
    due_date: date
    opening_balance: Decimal
    principal_due: Decimal
    interest_due: Decimal
    fee_due: Decimal
    total_due: Decimal
    closing_balance: Decimal
    interest_segments: tuple[InterestSegment, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "installment_number": self.installment_number,
            "period_start": self.period_start.isoformat(),
            "due_date": self.due_date.isoformat(),
            "opening_balance": str(money(self.opening_balance)),
            "principal_due": str(money(self.principal_due)),
            "interest_due": str(money(self.interest_due)),
            "fee_due": str(money(self.fee_due)),
            "total_due": str(money(self.total_due)),
            "closing_balance": str(money(self.closing_balance)),
            "interest_segments": [segment.as_dict() for segment in self.interest_segments],
        }


def _split_amount(total: Decimal, count: int) -> list[Decimal]:
    if count <= 0:
        raise ValueError("Count must be greater than zero")
    total_value = money(total)
    regular = money(total_value / Decimal(count))
    values = [regular for _ in range(count)]
    values[-1] = money(total_value - sum(values[:-1], Decimal("0")))
    return values


def _validate_inputs(
    principal: Decimal,
    rate_percent: Decimal,
    term_months: int,
    processing_fee: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    principal_value = money(principal)
    rate_value = Decimal(str(rate_percent or 0))
    fee_value = money(processing_fee or 0)
    if principal_value <= 0:
        raise ValueError("Principal must be greater than zero")
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if term_months > 120:
        raise ValueError("Term months cannot exceed 120")
    if rate_value < 0:
        raise ValueError("Rate cannot be negative")
    if fee_value < 0:
        raise ValueError("Processing fee cannot be negative")
    return principal_value, rate_value, fee_value


def _add_calendar_months(anchor: date, months: int) -> date:
    """Move *anchor* forward by calendar months without drifting at month-end.

    Examples:
    - 30 Jul -> 30 Aug -> 30 Sep
    - 31 Jan -> 28/29 Feb -> 31 Mar -> 30 Apr

    This is the same default schedule convention exposed by the frontend
    calculator. Explicit offer/approval due dates still take precedence.
    """
    month_index = (anchor.month - 1) + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    source_month_end = calendar.monthrange(anchor.year, anchor.month)[1]
    target_month_end = calendar.monthrange(year, month)[1]
    day = target_month_end if anchor.day == source_month_end else min(anchor.day, target_month_end)
    return date(year, month, day)


def generate_monthly_due_dates(start: date, term_months: int) -> list[date]:
    """Build LoanHub's default monthly proposal without weakening core validation.

    The public calculator may use this helper when a user has not supplied dates
    yet. Core lending calculations still require explicit dates so offers,
    approvals, contracts, and persisted schedules cannot silently invent them.
    """
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if term_months > 120:
        raise ValueError("Term months cannot exceed 120")
    return [_add_calendar_months(start, month) for month in range(1, term_months + 1)]


def _resolve_dates(
    *,
    term_months: int,
    start_date: date | None,
    due_dates: list[date] | tuple[date, ...] | None,
) -> tuple[date, date, list[date]]:
    """Validate the explicit repayment dates used by the core loan engine.

    Deliberately keep schedule generation outside this function. A calculator
    may propose dates before calling the engine, but persisted lending workflows
    must provide the exact agreed dates so a missing schedule is never silently
    converted into a different financial obligation.
    """
    resolved_start = start_date or date.today()
    if due_dates is None:
        raise ValueError(
            f"Enter exactly {term_months} installment due date{'s' if term_months != 1 else ''}"
        )
    resolved_due_dates = list(due_dates)

    if len(resolved_due_dates) != term_months:
        raise ValueError(
            f"Enter exactly {term_months} installment due date{'s' if term_months != 1 else ''}"
        )

    previous = resolved_start
    for index, due_date in enumerate(resolved_due_dates, start=1):
        if due_date <= previous:
            if index == 1:
                raise ValueError("Installment 1 due date must be after the interest start date")
            raise ValueError(f"Installment {index} due date must be after installment {index - 1}")
        previous = due_date

    return resolved_start, resolved_due_dates[0], resolved_due_dates


def _daily_segments(
    balance: Decimal,
    annual_rate_decimal: Decimal,
    start_date: date,
    end_date: date,
) -> tuple[Decimal, tuple[InterestSegment, ...]]:
    """Calculate Actual/Month interest using (start, end] day counting.

    This convention exactly matches the supplied spreadsheet examples:
    24 April to 24 May is split into 6 April days and 24 May days.
    """
    if end_date <= start_date or annual_rate_decimal == 0:
        return Decimal("0"), ()

    monthly_rate = annual_rate_decimal / TWELVE
    current = start_date + timedelta(days=1)
    raw_interest = Decimal("0")
    segments: list[InterestSegment] = []

    while current <= end_date:
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, days_in_month)
        segment_end = min(month_end, end_date)
        days = (segment_end - current).days + 1
        segment_interest = money(balance * monthly_rate * Decimal(days) / Decimal(days_in_month))
        # Each calendar-month segment is rounded to cents before summing. This
        # matches banking spreadsheets that disclose and add the monthly
        # portions separately (for example 5.72 + 20.27 = 25.99).
        raw_interest += segment_interest
        segments.append(
            InterestSegment(
                period_start=current,
                period_end=segment_end,
                days=days,
                days_in_month=days_in_month,
                interest=segment_interest,
            )
        )
        current = segment_end + timedelta(days=1)

    return money(raw_interest), tuple(segments)


def _daily_period_factor(
    annual_rate_decimal: Decimal,
    start_date: date,
    end_date: date,
) -> Decimal:
    if annual_rate_decimal == 0:
        return Decimal("0")
    monthly_rate = annual_rate_decimal / TWELVE
    current = start_date + timedelta(days=1)
    factor = Decimal("0")
    while current <= end_date:
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        segment_end = min(date(current.year, current.month, days_in_month), end_date)
        days = (segment_end - current).days + 1
        factor += monthly_rate * Decimal(days) / Decimal(days_in_month)
        current = segment_end + timedelta(days=1)
    return factor


def calculate_daily_accrued_interest(
    balance: Decimal,
    annual_rate_percent: Decimal,
    start_date: date,
    end_date: date,
) -> tuple[Decimal, list[dict[str, Any]]]:
    """Public helper for statement previews, tests and arrears calculations."""
    principal_value = money(balance)
    annual_rate_decimal = Decimal(str(annual_rate_percent)) / HUNDRED
    interest, segments = _daily_segments(
        principal_value,
        annual_rate_decimal,
        start_date,
        end_date,
    )
    return interest, [segment.as_dict() for segment in segments]


def _rows_from_parts(
    *,
    principal_parts: Iterable[Decimal],
    interest_parts: Iterable[Decimal],
    fee_parts: Iterable[Decimal],
    schedule_amounts: Iterable[Decimal] | None,
    start_date: date,
    due_dates: list[date],
) -> list[ScheduleRow]:
    principals = list(principal_parts)
    interests = list(interest_parts)
    fees = list(fee_parts)
    totals = list(schedule_amounts) if schedule_amounts is not None else []
    opening = money(sum(principals, Decimal("0")))
    previous_date = start_date
    rows: list[ScheduleRow] = []

    for index, due_date in enumerate(due_dates):
        principal_due = money(principals[index])
        interest_due = money(interests[index])
        fee_due = money(fees[index])
        total_due = money(totals[index]) if totals else money(principal_due + interest_due + fee_due)
        if index == len(due_dates) - 1:
            principal_due = opening
            total_due = money(principal_due + interest_due + fee_due) if not totals else total_due
        closing = money(max(opening - principal_due, Decimal("0")))
        rows.append(
            ScheduleRow(
                installment_number=index + 1,
                period_start=previous_date,
                due_date=due_date,
                opening_balance=opening,
                principal_due=principal_due,
                interest_due=interest_due,
                fee_due=fee_due,
                total_due=total_due,
                closing_balance=closing,
            )
        )
        opening = closing
        previous_date = due_date
    return rows


def _micro_loan_rows(
    principal: Decimal,
    rate_percent: Decimal,
    term_months: int,
    processing_fee: Decimal,
    start_date: date,
    due_dates: list[date],
) -> tuple[list[ScheduleRow], dict[str, Any]]:
    factor = Decimal("1") + (rate_percent / HUNDRED)
    running_balance = principal
    components: list[Decimal] = []
    steps: list[dict[str, Any]] = []

    for month_number in range(1, term_months + 1):
        opening_balance = running_balance
        amount_after_rate = money(opening_balance * factor)
        if month_number < term_months:
            component = money(amount_after_rate / Decimal("2"))
            carried_balance = money(amount_after_rate - component)
        else:
            component = amount_after_rate
            carried_balance = Decimal("0.00")
        components.append(component)
        steps.append(
            {
                "month": month_number,
                "opening_balance": str(opening_balance),
                "amount_after_rate": str(amount_after_rate),
                "component_amount": str(component),
                "carried_balance": str(carried_balance),
            }
        )
        running_balance = carried_balance

    total = money(sum(components, Decimal("0")) + processing_fee)
    schedule_amounts = _split_amount(total, term_months)
    principal_parts = _split_amount(principal, term_months)
    fee_parts = _split_amount(processing_fee, term_months)
    interest_parts: list[Decimal] = []
    for total_due, principal_due, fee_due in zip(schedule_amounts, principal_parts, fee_parts):
        interest_parts.append(money(max(total_due - principal_due - fee_due, Decimal("0"))))
    expected_interest = money(total - principal - processing_fee)
    interest_parts[-1] = money(expected_interest - sum(interest_parts[:-1], Decimal("0")))

    rows = _rows_from_parts(
        principal_parts=principal_parts,
        interest_parts=interest_parts,
        fee_parts=fee_parts,
        schedule_amounts=schedule_amounts,
        start_date=start_date,
        due_dates=due_dates,
    )
    return rows, {"components": [str(value) for value in components], "steps": steps}


def _simple_or_flat_rows(
    principal: Decimal,
    annual_rate_decimal: Decimal,
    term_months: int,
    processing_fee: Decimal,
    start_date: date,
    due_dates: list[date],
) -> list[ScheduleRow]:
    total_interest = money(principal * annual_rate_decimal * Decimal(term_months) / TWELVE)
    return _rows_from_parts(
        principal_parts=_split_amount(principal, term_months),
        interest_parts=_split_amount(total_interest, term_months),
        fee_parts=_split_amount(processing_fee, term_months),
        schedule_amounts=None,
        start_date=start_date,
        due_dates=due_dates,
    )


def _compound_rows(
    principal: Decimal,
    annual_rate_decimal: Decimal,
    term_months: int,
    processing_fee: Decimal,
    start_date: date,
    due_dates: list[date],
) -> list[ScheduleRow]:
    monthly_rate = annual_rate_decimal / TWELVE
    notional = principal
    interest_parts: list[Decimal] = []
    for _ in range(term_months):
        interest = money(notional * monthly_rate)
        interest_parts.append(interest)
        notional = money(notional + interest)
    exact_total_interest = money(principal * ((Decimal("1") + monthly_rate) ** term_months - Decimal("1")))
    interest_parts[-1] = money(exact_total_interest - sum(interest_parts[:-1], Decimal("0")))
    return _rows_from_parts(
        principal_parts=_split_amount(principal, term_months),
        interest_parts=interest_parts,
        fee_parts=_split_amount(processing_fee, term_months),
        schedule_amounts=None,
        start_date=start_date,
        due_dates=due_dates,
    )


def _reducing_rows(
    principal: Decimal,
    annual_rate_decimal: Decimal,
    term_months: int,
    processing_fee: Decimal,
    start_date: date,
    due_dates: list[date],
) -> list[ScheduleRow]:
    monthly_rate = annual_rate_decimal / TWELVE
    if monthly_rate == 0:
        base_payment = money(principal / Decimal(term_months))
    else:
        with localcontext() as ctx:
            ctx.prec = 40
            growth = (Decimal("1") + monthly_rate) ** term_months
            base_payment = money(principal * monthly_rate * growth / (growth - Decimal("1")))

    fee_parts = _split_amount(processing_fee, term_months)
    opening = principal
    previous_date = start_date
    rows: list[ScheduleRow] = []
    for index, due_date in enumerate(due_dates):
        interest_due = money(opening * monthly_rate)
        if index == term_months - 1:
            principal_due = opening
        else:
            principal_due = money(max(base_payment - interest_due, Decimal("0")))
            principal_due = min(principal_due, opening)
        closing = money(max(opening - principal_due, Decimal("0")))
        total_due = money(principal_due + interest_due + fee_parts[index])
        rows.append(
            ScheduleRow(
                installment_number=index + 1,
                period_start=previous_date,
                due_date=due_date,
                opening_balance=opening,
                principal_due=principal_due,
                interest_due=interest_due,
                fee_due=fee_parts[index],
                total_due=total_due,
                closing_balance=closing,
            )
        )
        opening = closing
        previous_date = due_date
    return rows


def _daily_reducing_rows(
    principal: Decimal,
    annual_rate_decimal: Decimal,
    term_months: int,
    processing_fee: Decimal,
    start_date: date,
    due_dates: list[date],
) -> list[ScheduleRow]:
    factors: list[Decimal] = []
    period_start = start_date
    for due_date in due_dates:
        factors.append(_daily_period_factor(annual_rate_decimal, period_start, due_date))
        period_start = due_date

    if annual_rate_decimal == 0:
        base_payment = money(principal / Decimal(term_months))
    else:
        with localcontext() as ctx:
            ctx.prec = 40
            cumulative = Decimal("1")
            discount_sum = Decimal("0")
            for factor in factors:
                cumulative *= Decimal("1") + factor
                discount_sum += Decimal("1") / cumulative
            base_payment = money(principal / discount_sum)

    fee_parts = _split_amount(processing_fee, term_months)
    opening = principal
    previous_date = start_date
    rows: list[ScheduleRow] = []
    for index, due_date in enumerate(due_dates):
        interest_due, segments = _daily_segments(
            opening,
            annual_rate_decimal,
            previous_date,
            due_date,
        )
        if index == term_months - 1:
            principal_due = opening
        else:
            principal_due = money(max(base_payment - interest_due, Decimal("0")))
            principal_due = min(principal_due, opening)
        closing = money(max(opening - principal_due, Decimal("0")))
        total_due = money(principal_due + interest_due + fee_parts[index])
        rows.append(
            ScheduleRow(
                installment_number=index + 1,
                period_start=previous_date,
                due_date=due_date,
                opening_balance=opening,
                principal_due=principal_due,
                interest_due=interest_due,
                fee_due=fee_parts[index],
                total_due=total_due,
                closing_balance=closing,
                interest_segments=segments,
            )
        )
        opening = closing
        previous_date = due_date
    return rows


def calculate_loan_terms(
    *,
    principal: Decimal,
    rate_percent: Decimal,
    term_months: int,
    processing_fee: Decimal = Decimal("0"),
    interest_method: LoanCalculationMethod | str = LoanCalculationMethod.MICRO_LOAN,
    start_date: date | None = None,
    first_payment_date: date | None = None,
    due_dates: list[date] | tuple[date, ...] | None = None,
) -> tuple[Decimal, Decimal, dict[str, Any]]:
    """Calculate a complete, auditable loan schedule for every LoanHub flow."""
    principal_value, rate_value, fee_value = _validate_inputs(
        principal,
        rate_percent,
        term_months,
        processing_fee,
    )
    method = normalize_interest_method(interest_method)
    resolved_start_date = start_date or date.today()
    resolved_due_dates = due_dates
    if resolved_due_dates is None and first_payment_date is not None:
        if first_payment_date <= resolved_start_date:
            raise ValueError("first_payment_date must be after the interest start date")
        resolved_due_dates = [first_payment_date] + [
            _add_calendar_months(first_payment_date, month)
            for month in range(1, term_months)
        ]
    resolved_start, resolved_first_payment, due_dates = _resolve_dates(
        term_months=term_months,
        start_date=resolved_start_date,
        due_dates=resolved_due_dates,
    )
    annual_rate_decimal = rate_value / HUNDRED
    extra: dict[str, Any] = {}

    if method == LoanCalculationMethod.MICRO_LOAN:
        rows, extra = _micro_loan_rows(
            principal_value,
            rate_value,
            term_months,
            fee_value,
            resolved_start,
            due_dates,
        )
    elif method in {LoanCalculationMethod.SIMPLE_INTEREST, LoanCalculationMethod.FLAT_RATE}:
        rows = _simple_or_flat_rows(
            principal_value,
            annual_rate_decimal,
            term_months,
            fee_value,
            resolved_start,
            due_dates,
        )
    elif method == LoanCalculationMethod.COMPOUND_INTEREST:
        rows = _compound_rows(
            principal_value,
            annual_rate_decimal,
            term_months,
            fee_value,
            resolved_start,
            due_dates,
        )
    elif method == LoanCalculationMethod.REDUCING_BALANCE:
        rows = _reducing_rows(
            principal_value,
            annual_rate_decimal,
            term_months,
            fee_value,
            resolved_start,
            due_dates,
        )
    elif method == LoanCalculationMethod.DAILY_ACCRUAL_REDUCING:
        rows = _daily_reducing_rows(
            principal_value,
            annual_rate_decimal,
            term_months,
            fee_value,
            resolved_start,
            due_dates,
        )
    else:  # pragma: no cover - normalize_interest_method already rejects this.
        raise ValueError(f"Unsupported interest method: {method.value}")

    total_interest = money(sum((row.interest_due for row in rows), Decimal("0")))
    total_repayable = money(sum((row.total_due for row in rows), Decimal("0")))
    schedule_amounts = [money(row.total_due) for row in rows]
    monthly_installment = schedule_amounts[0]
    maturity_date = due_dates[-1]

    details: dict[str, Any] = {
        "method": method.value,
        "method_label": INTEREST_METHOD_LABELS[method],
        "rate_basis": interest_rate_basis(method),
        "principal": str(principal_value),
        "rate_percent": str(rate_value),
        "months": term_months,
        "processing_fee": str(fee_value),
        "interest_start_date": resolved_start.isoformat(),
        "first_payment_date": resolved_first_payment.isoformat(),
        "maturity_date": maturity_date.isoformat(),
        "total_interest": str(total_interest),
        "total_repayable": str(total_repayable),
        "monthly_installment": str(monthly_installment),
        "schedule_amounts": [str(value) for value in schedule_amounts],
        "schedule_rows": [row.as_dict() for row in rows],
        **extra,
    }
    return monthly_installment, total_repayable, details
