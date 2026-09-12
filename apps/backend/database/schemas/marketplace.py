from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from database.models.enums import LoanRequestStatus


class MarketplaceBorrowerSummary(BaseModel):
    district: str | None
    employment_status: str
    monthly_income_band: str | None
    has_existing_loans: bool


class MarketplaceRequestCard(BaseModel):
    id: UUID
    requested_amount: Decimal
    preferred_term_months: int | None
    loan_purpose: str | None
    status: LoanRequestStatus
    allow_lenders_to_call: bool
    created_at: datetime
    expires_at: datetime | None
    is_unlocked: bool
    unlock_price: Decimal
    borrower: MarketplaceBorrowerSummary


class MarketplaceEvidenceDocument(BaseModel):
    id: UUID
    category: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class MarketplaceBorrowerDetail(BaseModel):
    borrower_id: UUID
    user_id: UUID
    full_name: str
    phone: str
    email: str | None
    gender: str | None
    date_of_birth: str | None
    national_id: str | None
    passport_number: str | None
    district: str | None
    town_or_village: str | None
    physical_address: str | None

    employment_status: str
    employment_type: str | None
    employer_name: str | None
    job_title: str | None
    employment_start_date: str | None
    monthly_income: Decimal | None
    net_monthly_income: Decimal | None
    other_monthly_income: Decimal
    other_income_source: str | None

    monthly_living_expenses: Decimal
    monthly_debt_repayments: Decimal
    dependants: int
    residential_status: str | None
    years_at_address: int | None
    existing_loan_total: Decimal

    bank_name: str | None
    account_holder_name: str | None
    account_last_four: str | None

    consent_to_credit_checks: bool
    consent_to_share_documents: bool
    total_monthly_income: Decimal
    total_monthly_commitments: Decimal
    disposable_monthly_income: Decimal
    debt_to_income_percent: Decimal | None
    profile_completeness: int
    missing_requirements: list[str]
    evidence_documents: list[MarketplaceEvidenceDocument]


class MarketplaceRequestDetail(MarketplaceRequestCard):
    borrower_detail: MarketplaceBorrowerDetail | None
