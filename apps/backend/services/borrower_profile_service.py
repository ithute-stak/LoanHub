from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Protocol

from database.models.enums import InstallmentStatus, LoanStatus, PaymentStatus
from database.schemas.company_clients import CompanyClientPaymentRatingRead


class InstallmentLike(Protocol):
    status: object
    total_due: object
    paid_amount: object
    paid_at: datetime | None
    due_date: date


class LoanLike(Protocol):
    status: object


class PaymentLike(Protocol):
    status: object
    completed_at: datetime | None
    created_at: datetime | None


def enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def utc_sort_value(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_payment_rating(
    installments: Iterable[InstallmentLike],
    loans: Iterable[LoanLike],
    payments: Iterable[PaymentLike],
    *,
    today: date | None = None,
) -> CompanyClientPaymentRatingRead:
    """Calculate a transparent company-only repayment rating.

    Future installments and waived installments are excluded. A paid
    installment contributes to completion, while only a timestamped payment on
    or before the due date contributes to the on-time score. Past-due unpaid
    installments and defaulted loans reduce the result.
    """
    today = today or date.today()
    installments = list(installments)
    loans = list(loans)
    payments = list(payments)

    paid_installments = 0
    on_time_installments = 0
    late_installments = 0
    overdue_installments = 0
    undated_paid_installments = 0
    late_days: list[int] = []
    total_due_amount = Decimal("0")
    total_paid_amount = Decimal("0")
    paid_dates: list[datetime] = []
    total_due_installments = 0

    for installment in installments:
        status_value = enum_value(installment.status)
        if status_value == InstallmentStatus.WAIVED.value:
            continue

        due_amount = max(Decimal(installment.total_due or 0), Decimal("0"))
        paid_amount = max(Decimal(installment.paid_amount or 0), Decimal("0"))
        paid_in_full = (
            status_value == InstallmentStatus.PAID.value
            or (due_amount > 0 and paid_amount + Decimal("0.01") >= due_amount)
        )
        due_date = installment.due_date

        if not paid_in_full and due_date >= today:
            continue

        total_due_installments += 1
        total_due_amount += due_amount
        total_paid_amount += paid_amount

        if paid_in_full:
            paid_installments += 1
            paid_at = installment.paid_at
            if paid_at is None:
                undated_paid_installments += 1
            else:
                paid_dates.append(paid_at)
                days_late = (paid_at.date() - due_date).days
                if days_late <= 0:
                    on_time_installments += 1
                else:
                    late_installments += 1
                    late_days.append(days_late)
        else:
            overdue_installments += 1

    payment_dates = [
        payment.completed_at or payment.created_at
        for payment in payments
        if enum_value(payment.status) == PaymentStatus.SUCCEEDED.value
        and (payment.completed_at or payment.created_at) is not None
    ]
    all_payment_dates = paid_dates + payment_dates
    last_payment_at = (
        max(all_payment_dates, key=utc_sort_value)
        if all_payment_dates
        else None
    )

    if total_due_installments == 0:
        return CompanyClientPaymentRatingRead(
            score=None,
            grade="NR",
            label="Not rated",
            has_history=False,
            explanation=(
                "No completed or overdue installment is available yet. "
                "The rating will begin after the borrower develops payment history with this company."
            ),
            total_due_amount=total_due_amount,
            total_paid_amount=total_paid_amount,
            last_payment_at=last_payment_at,
        )

    on_time_rate = on_time_installments / total_due_installments
    completion_rate = paid_installments / total_due_installments
    overdue_rate = overdue_installments / total_due_installments
    defaulted_loans = sum(
        1 for loan in loans
        if enum_value(loan.status) == LoanStatus.DEFAULTED.value
    )
    completed_loans = sum(
        1 for loan in loans
        if enum_value(loan.status) == LoanStatus.COMPLETED.value
    )

    score = round(
        (70 * on_time_rate)
        + (30 * completion_rate)
        - (25 * overdue_rate)
        - min(25, defaulted_loans * 10)
    )
    if completed_loans > 0 and overdue_installments == 0 and defaulted_loans == 0:
        score += 5
    score = max(0, min(100, score))

    if score >= 90:
        grade, label = "A", "Excellent"
    elif score >= 80:
        grade, label = "B", "Good"
    elif score >= 70:
        grade, label = "C", "Fair"
    elif score >= 60:
        grade, label = "D", "Weak"
    else:
        grade, label = "E", "High risk"

    explanation = (
        f"Based on {total_due_installments} due installment"
        f"{'s' if total_due_installments != 1 else ''}: "
        f"{on_time_installments} on time, {late_installments} late, "
        f"{overdue_installments} overdue"
        f"{f', and {undated_paid_installments} paid without a payment date' if undated_paid_installments else ''}. "
        "This rating uses only repayment history held by the active company."
    )

    return CompanyClientPaymentRatingRead(
        score=score,
        grade=grade,
        label=label,
        has_history=True,
        explanation=explanation,
        total_due_installments=total_due_installments,
        paid_installments=paid_installments,
        on_time_installments=on_time_installments,
        late_installments=late_installments,
        overdue_installments=overdue_installments,
        undated_paid_installments=undated_paid_installments,
        on_time_rate=round(on_time_rate, 4),
        completion_rate=round(completion_rate, 4),
        average_days_late=(
            round(sum(late_days) / len(late_days), 1)
            if late_days
            else 0
        ),
        total_due_amount=total_due_amount,
        total_paid_amount=total_paid_amount,
        last_payment_at=last_payment_at,
    )

BORROWER_EVIDENCE_LABELS = {
    "borrower_identity": "National ID or passport",
    "borrower_proof_of_address": "Proof of address",
    "borrower_payslip": "Recent payslip or income proof",
    "borrower_bank_statement": "Recent bank statement",
    "borrower_employment": "Employment letter or contract",
    "borrower_existing_debt": "Existing loan statement",
    "borrower_business": "Business registration or trading evidence",
    "borrower_other": "Other supporting evidence",
}


class BorrowerEvaluationLike(Protocol):
    employment_status: object
    employer_name: str | None
    job_title: str | None
    employment_start_date: date | None
    monthly_income: object
    net_monthly_income: object
    other_monthly_income: object
    monthly_living_expenses: object
    monthly_debt_repayments: object
    has_existing_loans: bool
    residential_status: str | None
    bank_name: str | None
    account_last_four: str | None
    consent_to_share_profile: bool
    consent_to_share_documents: bool
    consent_to_credit_checks: bool


class PersonEvaluationLike(Protocol):
    national_id: str | None
    passport_number: str | None
    district: str | None
    town_or_village: str | None
    physical_address: str | None


class EvidenceLike(Protocol):
    category: str


def _money(value: object) -> Decimal:
    return max(Decimal(value or 0), Decimal("0"))


def build_borrower_evaluation(
    borrower: BorrowerEvaluationLike,
    person: PersonEvaluationLike,
    evidence: Iterable[EvidenceLike],
) -> dict[str, object]:
    """Build explainable affordability totals and a non-decisional completeness score.

    The result helps a lender find missing evidence. It deliberately does not
    approve, reject or assign a credit-risk grade.
    """
    base_income = (
        _money(borrower.net_monthly_income)
        if borrower.net_monthly_income is not None
        else _money(borrower.monthly_income)
    )
    total_income = base_income + _money(borrower.other_monthly_income)
    living_expenses = _money(borrower.monthly_living_expenses)
    debt_repayments = _money(borrower.monthly_debt_repayments)
    commitments = living_expenses + debt_repayments
    disposable_income = total_income - commitments
    debt_to_income = (
        (debt_repayments / total_income * Decimal("100")).quantize(Decimal("0.01"))
        if total_income > 0
        else None
    )

    categories = {item.category for item in evidence}
    employment_status = enum_value(borrower.employment_status)
    employment_complete = employment_status in {"unemployed", "student", "pensioner"} or bool(
        borrower.employer_name and borrower.job_title
    )
    employment_evidence = bool(
        categories
        & {"borrower_payslip", "borrower_employment", "borrower_business"}
    )

    checks = [
        ("Government-issued identity number", bool(person.national_id or person.passport_number)),
        ("Complete residential address", bool(person.district and person.town_or_village and person.physical_address)),
        ("Employment details", employment_complete),
        ("Monthly income", total_income > 0),
        ("Monthly living expenses", living_expenses > 0),
        ("Existing debt repayments", not borrower.has_existing_loans or debt_repayments > 0),
        ("Residential status", bool(borrower.residential_status)),
        ("Bank identity (name and last four digits only)", bool(borrower.bank_name and borrower.account_last_four)),
        ("Profile-sharing consent", bool(borrower.consent_to_share_profile)),
        ("Credit-check consent", bool(borrower.consent_to_credit_checks)),
        ("Evidence-sharing consent", bool(borrower.consent_to_share_documents)),
        ("Identity document", "borrower_identity" in categories),
        ("Proof of address", "borrower_proof_of_address" in categories),
        ("Income or employment evidence", employment_evidence),
        ("Bank statement", "borrower_bank_statement" in categories),
    ]
    completed = sum(1 for _, present in checks if present)
    return {
        "total_monthly_income": total_income,
        "total_monthly_commitments": commitments,
        "disposable_monthly_income": disposable_income,
        "debt_to_income_percent": debt_to_income,
        "profile_completeness": round(completed / len(checks) * 100),
        "missing_requirements": [label for label, present in checks if not present],
    }
