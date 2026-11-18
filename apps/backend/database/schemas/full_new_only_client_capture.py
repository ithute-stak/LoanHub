"""Phase 84: complete staff-registration capture contract, with no writer.

This class preserves the entire existing assisted client registration command
and rejects unexpected fields. It is NOT connected to a public route or the
minimal atomic writer, which deliberately rejects full financial details.
"""
from __future__ import annotations

from datetime import date
from pydantic import ConfigDict, model_validator

from database.schemas.company_clients import AssistedCompanyClientCreate


class FullNewOnlyClientCapture(AssistedCompanyClientCreate):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def enforce_new_only_capture_evidence(self):
        if self.branch_id is None:
            raise ValueError("Branch is required for staff registration")
        if self.date_of_birth >= date.today():
            raise ValueError("Date of birth must be in the past")
        if not any((value or "").strip() for value in (
            self.national_id, self.passport_number
        )):
            raise ValueError("National ID or passport number is required")

        # A declared external liability cannot be silently discarded,
        # reduced to a guessed zero, or later written as a new LoanHub loan.
        if self.external_debts and not self.has_existing_loans:
            raise ValueError("Declare existing loans when external debts are supplied")
        if self.external_debts and self.existing_loan_total <= 0 and any(
            debt.current_balance > 0 for debt in self.external_debts
        ):
            raise ValueError("Existing-loan total must reflect declared debts")
        if self.has_existing_loans and self.existing_loan_total <= 0 and not any(
            debt.current_balance > 0 for debt in self.external_debts
        ):
            raise ValueError("Existing loans require an outstanding amount")
        return self

    def to_internal_full_payload(self) -> AssistedCompanyClientCreate:
        """Preserve all supported fields; never invoke a registration writer."""
        return AssistedCompanyClientCreate.model_validate(
            self.model_dump(mode="python", exclude_none=False)
        )
