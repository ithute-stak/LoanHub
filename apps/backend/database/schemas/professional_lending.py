from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DirectApplicationCreate(BaseModel):
    borrower_id: UUID
    branch_id: UUID | None = None
    product_id: UUID | None = None
    requested_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    term_count: int = Field(gt=0, le=120)
    repayment_type: str = Field(default="monthly", pattern="^monthly$")
    purpose: str | None = Field(default=None, max_length=5000)
    installment_due_dates: list[date] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_due_dates(self):
        if len(self.installment_due_dates) != self.term_count:
            raise ValueError(f"Enter exactly {self.term_count} installment due dates")
        for index in range(1, len(self.installment_due_dates)):
            if self.installment_due_dates[index] <= self.installment_due_dates[index - 1]:
                raise ValueError(f"Installment {index + 1} due date must be after installment {index}")
        return self


class DirectApplicationApprove(BaseModel):
    product_id: UUID | None = None
    approved_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    interest_rate: Decimal | None = Field(default=None, ge=0, le=100)
    processing_fee: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    installment_due_dates: list[date] = Field(min_length=1, max_length=120)
    decision_notes: str | None = Field(default=None, max_length=2000)


class DirectApplicationReview(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class DirectApplicationReject(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class SuggestionCreate(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    category: str = "feature_request"
    description: str = Field(min_length=10, max_length=10000)
    priority: str = "normal"


class SuggestionUpdate(BaseModel):
    status: str
    platform_response: str | None = None


class WallPostCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10, max_length=5000)
    product_id: UUID | None = None
    branch_id: UUID | None = None
    terms: dict = Field(default_factory=dict)
    expires_at: datetime | None = None
    publish: bool = False


class PrintAgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class PrintJobCreate(BaseModel):
    agent_id: UUID
    file_id: UUID
    printer_name: str | None = None
    copies: int = Field(default=1, ge=1, le=20)


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    current_path: str | None = None
