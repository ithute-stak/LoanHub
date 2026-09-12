from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from database.models.enums import RepaymentType
from utils.banking import standard_bank_fields, validate_account_number_for_bank


IdentityType = Literal["national_id", "passport"]
LegacyCaptureStatus = Literal["draft", "reviewed", "returned", "posted"]


def normalise_legacy_capture_status(value: str) -> LegacyCaptureStatus:
    """Make historic pre-register rows safe for the modern register response."""

    if value in {"posted", "converted"}:
        return "posted"
    if value in {"draft", "reviewed", "returned"}:
        return value
    raise ValueError(f"Unsupported legacy cash-out status: {value}")


class LegacyCashoutCaptureCreate(BaseModel):
    """A faithful, progressively completed cash-out-book transcription."""

    model_config = ConfigDict(extra="forbid")

    branch_id: UUID | None = None
    folio_number: str = Field(min_length=1, max_length=80)
    cashout_book_number: str | None = Field(default=None, max_length=80)
    page_number: str | None = Field(default=None, max_length=80)
    entry_number: str | None = Field(default=None, max_length=80)
    loan_date: date

    # A draft can be captured while staff are working through an old book.
    # These details become mandatory only when the reviewer approves posting.
    first_names: str | None = Field(default=None, max_length=220)
    surname: str | None = Field(default=None, max_length=100)
    identity_number: str | None = Field(default=None, max_length=100)
    passport_expiry_date: date | None = None
    identity_type: IdentityType | None = None

    residential_address: str | None = Field(default=None, max_length=2000)
    postal_address: str | None = Field(default=None, max_length=1000)
    employer: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=150)
    net_salary: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)

    cell_phone: str | None = Field(default=None, max_length=30)
    home_phone: str | None = Field(default=None, max_length=30)
    work_phone: str | None = Field(default=None, max_length=30)
    emergency_name: str | None = Field(default=None, max_length=200)
    emergency_cell_phone: str | None = Field(default=None, max_length=30)
    emergency_work_phone: str | None = Field(default=None, max_length=30)
    emergency_relationship: str | None = Field(default=None, max_length=100)

    # Banking details are required at capture and saved encrypted. The full
    # account number is never returned by this API or displayed in the register.
    bank_name: str = Field(min_length=2, max_length=160)
    bank_account_holder: str = Field(min_length=2, max_length=200)
    bank_account_number: str = Field(min_length=4, max_length=40)
    bank_branch_name: str | None = Field(default=None, max_length=160)
    bank_branch_code: str | None = Field(default=None, max_length=40)
    bank_account_type: str = Field(default="savings", min_length=2, max_length=40)

    amount_taken: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    total_repayable: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    installment_count: int = Field(default=0, ge=0, le=600)
    installment_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    repayment_type: RepaymentType = RepaymentType.MONTHLY
    calculator_method: str | None = Field(default=None, max_length=80)
    calculator_snapshot: dict = Field(default_factory=dict)
    capture_notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def classify_identity_and_validate_history(self):
        self.folio_number = self.folio_number.strip()
        if self.identity_number:
            self.identity_number = "".join(self.identity_number.split()).upper()
        if self.first_names:
            self.first_names = self.first_names.strip() or None
        if self.surname:
            self.surname = self.surname.strip() or None

        if not self.folio_number:
            raise ValueError("Folio number is required")
        if self.loan_date > date.today():
            raise ValueError("Loan date cannot be in the future")
        if self.total_repayable > 0 and self.amount_paid > self.total_repayable:
            raise ValueError("Amount paid cannot exceed the recorded total repayable")

        try:
            bank_name, bank_branch_name, bank_branch_code = standard_bank_fields(self.bank_name)
            account_number = validate_account_number_for_bank(bank_name, self.bank_account_number)
        except ValueError as error:
            raise ValueError(str(error)) from error
        if account_number is None:
            raise ValueError("A valid bank account number is required")
        self.bank_name = bank_name
        self.bank_branch_name = bank_branch_name
        self.bank_branch_code = bank_branch_code
        self.bank_account_number = account_number

        if not self.identity_number:
            if self.passport_expiry_date is not None:
                raise ValueError("Passport expiry date requires a passport number")
            self.identity_type = None
        elif self.identity_number.isdigit():
            self.identity_type = "national_id"
            if self.passport_expiry_date is not None:
                raise ValueError("Lesotho national IDs do not have an expiry date")
        elif any(character.isalpha() for character in self.identity_number):
            self.identity_type = "passport"
            if self.passport_expiry_date is None:
                raise ValueError("Passport expiry date is required when the identity number contains letters")
        else:
            raise ValueError("Identity number must contain only digits for a national ID or letters for a passport")

        return self


class LegacyCashoutReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve_for_posting: bool
    verified_against_cashout_book: bool
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_book_verification_for_approval(self):
        if self.approve_for_posting and not self.verified_against_cashout_book:
            raise ValueError("Confirm that the entry was checked against the original cash-out book before approving it")
        return self


class LegacyCashoutCaptureRead(BaseModel):
    id: UUID
    folio_number: str
    cashout_book_number: str | None = None
    page_number: str | None = None
    entry_number: str | None = None
    loan_date: date | None = None

    borrower_name: str
    # The secure company workflow needs these values to continue an incomplete
    # entry. The bank account number itself is deliberately never returned.
    first_names: str | None = None
    surname: str | None = None
    identity_number: str | None = None
    identity_type: IdentityType | None = None
    passport_expiry_date: date | None = None
    residential_address: str | None = None
    postal_address: str | None = None
    employer: str | None = None
    occupation: str | None = None
    net_salary: Decimal | None = None
    cell_phone: str | None = None
    home_phone: str | None = None
    work_phone: str | None = None
    emergency_name: str | None = None
    emergency_cell_phone: str | None = None
    emergency_work_phone: str | None = None
    emergency_relationship: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_branch_name: str | None = None
    bank_branch_code: str | None = None
    bank_account_type: str | None = None
    bank_account_last4: str | None = None
    has_bank_account_number: bool = False
    amount_taken: Decimal
    total_repayable: Decimal
    amount_paid: Decimal
    balance: Decimal
    installment_count: int
    installment_amount: Decimal
    repayment_type: str
    calculator_method: str | None = None
    calculator_snapshot: dict = Field(default_factory=dict)
    capture_notes: str | None = None
    status: LegacyCaptureStatus
    review_notes: str | None = None
    loan_reference: str | None = None
    borrower_profile_ready: bool = False
    created_at: datetime
    reviewed_at: datetime | None = None
    converted_at: datetime | None = None
