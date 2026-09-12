from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from database.models.enums import LoanCalculationMethod
from services.interest_calculation_service import calculate_loan_terms


router = APIRouter(
    prefix="/loans",
    tags=["Loan calculation compatibility"],
)


class LoanCalculationRequest(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    rate_percent: Decimal = Field(ge=0, max_digits=8, decimal_places=4)
    months: int = Field(ge=1, le=120)
    processing_fee: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=15,
        decimal_places=2,
    )
    interest_method: LoanCalculationMethod = LoanCalculationMethod.MICRO_LOAN
    interest_start_date: date | None = None
    due_dates: list[date] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_manual_due_dates(self):
        if len(self.due_dates) != self.months:
            raise ValueError(f"Enter exactly {self.months} installment due dates")
        previous = self.interest_start_date or date.today()
        for index, due_date in enumerate(self.due_dates, start=1):
            if due_date <= previous:
                if index == 1:
                    raise ValueError("Installment 1 due date must be after the interest start date")
                raise ValueError(f"Installment {index} due date must be after installment {index - 1}")
            previous = due_date
        return self


class InterestSegmentRead(BaseModel):
    period_start: date
    period_end: date
    days: int
    days_in_month: int
    interest: Decimal


class LoanCalculationScheduleRowRead(BaseModel):
    installment_number: int
    period_start: date
    due_date: date
    opening_balance: Decimal
    principal_due: Decimal
    interest_due: Decimal
    fee_due: Decimal
    total_due: Decimal
    closing_balance: Decimal
    interest_segments: list[InterestSegmentRead] = Field(default_factory=list)


class LoanCalculationRead(BaseModel):
    method: LoanCalculationMethod
    method_label: str
    rate_basis: str
    principal: Decimal
    rate_percent: Decimal
    months: int
    processing_fee: Decimal
    interest_start_date: date
    first_payment_date: date
    maturity_date: date
    total_interest: Decimal
    total_repayable: Decimal
    monthly_installment: Decimal
    schedule_amounts: list[Decimal]
    schedule: list[LoanCalculationScheduleRowRead]
    steps: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/calculator", response_model=LoanCalculationRead)
def calculate_loan(payload: LoanCalculationRequest):
    """Compatibility endpoint retained for the unified loan calculator.

    Later document/router patches may replace ``routers/loans.py`` and
    accidentally remove POST /loans/calculator. Keeping this small endpoint in
    an independent router prevents the calculator from being lost again.
    """
    try:
        monthly, total, details = calculate_loan_terms(
            principal=payload.principal,
            rate_percent=payload.rate_percent,
            term_months=payload.months,
            processing_fee=payload.processing_fee,
            interest_method=payload.interest_method,
            start_date=payload.interest_start_date,
            due_dates=payload.due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "method": details["method"],
        "method_label": details["method_label"],
        "rate_basis": details["rate_basis"],
        "principal": payload.principal,
        "rate_percent": payload.rate_percent,
        "months": payload.months,
        "processing_fee": payload.processing_fee,
        "interest_start_date": details["interest_start_date"],
        "first_payment_date": details["first_payment_date"],
        "maturity_date": details["maturity_date"],
        "total_interest": details["total_interest"],
        "total_repayable": total,
        "monthly_installment": monthly,
        "schedule_amounts": details["schedule_amounts"],
        "schedule": details["schedule_rows"],
        "steps": details.get("steps", []),
    }
