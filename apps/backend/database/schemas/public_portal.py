from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicPlatformStats(BaseModel):
    """Privacy-safe aggregate activity published on the LoanHub website."""

    model_config = ConfigDict(extra="forbid")

    approved_institutions: int = Field(ge=0)
    active_branches: int = Field(ge=0)
    borrower_profiles: int = Field(ge=0)
    company_client_accounts: int = Field(ge=0)
    loan_requests: int = Field(ge=0)
    loan_offers: int = Field(ge=0)
    loan_accounts: int = Field(ge=0)
    active_loans: int = Field(ge=0)
    completed_loans: int = Field(ge=0)
    employee_profiles: int = Field(ge=0)
    managed_files: int = Field(ge=0)
    generated_reports: int = Field(ge=0)
    updated_at: datetime
