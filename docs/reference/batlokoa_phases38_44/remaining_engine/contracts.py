"""Immutable cross-component value types. OFFLINE ONLY, no API/provider imports."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
import re

CENT = Decimal('0.01')
MAX_AMOUNT = Decimal('9999999999999999.99')
OPAQUE = re.compile(r'^[A-Za-z0-9_-]{8,128}$')
FINGERPRINT = re.compile(r'^[0-9a-f]{64}$')

class ContractError(ValueError):
    pass

def amount(value: Decimal, *, positive: bool = True) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractError('Finite Decimal amount required')
    if value < 0 or value > MAX_AMOUNT or (positive and value == 0):
        raise ContractError('Amount outside permitted range')
    if value != value.quantize(CENT):
        raise ContractError('Money must be exact cents')
    return value

def reference(value: str) -> str:
    if not isinstance(value, str) or not OPAQUE.fullmatch(value):
        raise ContractError('Invalid opaque reference')
    return value

def fingerprint(value: str) -> str:
    if not isinstance(value, str) or not FINGERPRINT.fullmatch(value):
        raise ContractError('Invalid fingerprint')
    return value

@dataclass(frozen=True, slots=True)
class TenantKey:
    company_id: UUID
    loan_id: UUID
    borrower_id: UUID

    def __post_init__(self) -> None:
        if not all(isinstance(v, UUID) for v in (self.company_id, self.loan_id, self.borrower_id)):
            raise ContractError('Trusted UUID tenant, borrower, loan identifiers required')

@dataclass(frozen=True, slots=True)
class Money:
    value: Decimal
    currency: str = 'LSL'

    def __post_init__(self) -> None:
        amount(self.value)
        if self.currency != 'LSL':
            raise ContractError('Only LSL supported by this contract')
