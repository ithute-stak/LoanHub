from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


Money = Decimal
_MONEY_QUANTUM = Decimal("0.01")


def parse_money(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid money value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid money value") from exc


def provider_money(value: Decimal) -> float:
    """Serialize Decimal to a JSON number only at the CDAS transport boundary."""
    return float(value.quantize(_MONEY_QUANTUM))


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CdasEmployeeRecord(_ProviderModel):
    EmployeeNo: str = Field(min_length=1)
    Name: str | None = None
    Surname: str | None = None
    DOB: str | None = None
    Department: str | None = None
    JoiningDate: str | None = None
    TerminationDate: str | None = None


class CdasDeductionRecord(_ProviderModel):
    DeductionID: int | None = None
    EmployeeNo: str | None = None
    ItemCode: str | None = None
    ReferenceNo: str | None = None
    DeductionStatus: int | None = None
    TotalInstallment: int | None = None
    DeductionAmount: Decimal | None = None
    PrincipalAmount: Decimal | None = None
    ReducingBalance: Decimal | None = None
    EffectiveDate: str | None = None
    EffectiveMonth: str | None = None


class CdasDocumentRecord(_ProviderModel):
    FileName: str | None = None
    DocumentTye: str | int | None = None
    Year: int | None = None
    Month: int | None = None
    Content: str | None = None


class CdasLifecyclePayload(BaseModel):
    request_type: Literal[1, 3, 4, 6, 10]
    deduction_id: int = Field(ge=0)
    employee_no: str = Field(min_length=1, max_length=100)
    loan_policy: Literal[1, 2]
    item_code: str = Field(min_length=1, max_length=100)
    deduction_amount: Decimal = Field(ge=Decimal("0"), max_digits=15, decimal_places=2)
    total_installment: int = Field(ge=0)
    principal_amount: Decimal = Field(ge=Decimal("0"), max_digits=15, decimal_places=2)
    effective_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    reference_no: str = Field(min_length=1, max_length=200)

    def provider_payload(self) -> dict[str, Any]:
        return {
            "RequestType": self.request_type,
            "DeductionID": self.deduction_id,
            "EmployeeNo": self.employee_no.strip(),
            "LoanPolicy": self.loan_policy,
            "ItemCode": self.item_code.strip(),
            "DeductionAmount": provider_money(self.deduction_amount),
            "TotalInstallment": self.total_installment,
            "PrincipalAmount": provider_money(self.principal_amount),
            "EffectiveMonth": self.effective_month,
            "ReferenceNo": self.reference_no.strip(),
        }

    def ledger_payload(self) -> dict[str, Any]:
        payload = self.provider_payload()
        payload["DeductionAmount"] = format(self.deduction_amount.quantize(_MONEY_QUANTUM), "f")
        payload["PrincipalAmount"] = format(self.principal_amount.quantize(_MONEY_QUANTUM), "f")
        return payload


class CdasModifyActivePayload(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    total_installment: int = Field(gt=0)
    deduction_amount: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)
    principal_amount: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)
    deduction_id: int = Field(ge=0)
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    def provider_payload(self) -> dict[str, Any]:
        return {
            "EmployeeNo": self.employee_no.strip(),
            "ItemCode": self.item_code.strip(),
            "TotalInstallment": self.total_installment,
            "DeductionAmount": provider_money(self.deduction_amount),
            "PrincipalAmount": provider_money(self.principal_amount),
            "DeductionID": self.deduction_id,
            "EffectiveDate": self.effective_date,
        }

    def ledger_payload(self) -> dict[str, Any]:
        payload = self.provider_payload()
        payload["DeductionAmount"] = format(self.deduction_amount.quantize(_MONEY_QUANTUM), "f")
        payload["PrincipalAmount"] = format(self.principal_amount.quantize(_MONEY_QUANTUM), "f")
        return payload


class CdasSettlementPayload(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    deduction_id: int = Field(ge=0)
    effective_date: str = Field(min_length=10, max_length=50)
    employee_no: str = Field(min_length=1, max_length=100)
    settlement_reason: int = Field(ge=1, le=4)

    def provider_payload(self) -> dict[str, Any]:
        return {
            "ItemCode": self.item_code.strip(),
            "DeductionID": self.deduction_id,
            "EffectiveDate": self.effective_date.strip(),
            "EmployeeNo": self.employee_no.strip(),
            "SettlementReason": self.settlement_reason,
        }

    def ledger_payload(self) -> dict[str, Any]:
        return self.provider_payload()


def validate_employee(payload: Any) -> dict[str, Any]:
    try:
        return CdasEmployeeRecord.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError("CDAS employee response does not match the documented contract") from exc


def validate_deduction(payload: Any) -> dict[str, Any]:
    try:
        return CdasDeductionRecord.model_validate(payload).model_dump(mode="json", exclude_none=False)
    except ValidationError as exc:
        raise ValueError("CDAS deduction response does not match the documented contract") from exc


def validate_deductions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("CDAS deductions response is not a list")
    return [validate_deduction(item) for item in payload]


def validate_document(payload: Any) -> dict[str, Any]:
    try:
        return CdasDocumentRecord.model_validate(payload).model_dump(mode="json", exclude_none=False)
    except ValidationError as exc:
        raise ValueError("CDAS document response does not match the documented contract") from exc
