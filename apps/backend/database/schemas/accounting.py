from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountingAccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=180)
    account_type: str
    normal_balance: str
    description: str | None = None
    parent_id: UUID | None = None
    branch_id: UUID | None = None

    @field_validator("account_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"asset", "liability", "equity", "revenue", "expense"}:
            raise ValueError("Invalid account type")
        return normalized

    @field_validator("normal_balance")
    @classmethod
    def valid_balance(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"debit", "credit"}:
            raise ValueError("Normal balance must be debit or credit")
        return normalized


class AccountingAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    is_active: bool | None = None


class AccountingAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_key: str
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    parent_id: UUID | None = None
    code: str
    name: str
    account_type: str
    normal_balance: str
    description: str | None = None
    is_system: bool
    is_active: bool
    created_at: datetime


class JournalLineCreate(BaseModel):
    account_id: UUID
    description: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    @model_validator(mode="after")
    def one_side_only(self):
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit cannot be negative")
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Each line must contain either a debit or a credit")
        return self


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    lines: list[JournalLineCreate]

    @field_validator("lines")
    @classmethod
    def enough_lines(cls, value: list[JournalLineCreate]) -> list[JournalLineCreate]:
        if len(value) < 2:
            raise ValueError("A journal entry needs at least two lines")
        return value


class JournalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    description: str | None = None
    debit: Decimal
    credit: Decimal
    account: AccountingAccountRead


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_key: str
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    entry_number: str
    entry_date: date
    description: str
    reference_type: str | None = None
    reference_id: str | None = None
    status: str
    total_debit: Decimal
    total_credit: Decimal
    posted_at: datetime | None = None
    created_at: datetime
    lines: list[JournalLineRead]


class TrialBalanceLine(BaseModel):
    account_id: UUID
    code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceRead(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal


class FinancialStatementLine(BaseModel):
    code: str
    name: str
    amount: Decimal


class FinancialStatementRead(BaseModel):
    statement: str
    from_date: date | None = None
    to_date: date
    sections: dict[str, list[FinancialStatementLine]]
    totals: dict[str, Decimal]
