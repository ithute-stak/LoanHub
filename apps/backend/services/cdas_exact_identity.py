from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.lending_operations import CDASPayrollProfile
from database.models.person import Person
from database.models.user import User


class CdasExactIdentityError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class ResolvedCdasBorrower:
    borrower: Borrower
    account: CompanyBorrowerAccount
    person: Person


_PROVIDER_NATIONAL_ID_KEYS = (
    "NationalID",
    "NationalId",
    "nationalID",
    "nationalId",
    "national_id",
    "IDNumber",
    "IdNumber",
    "idNumber",
    "id_number",
    "IdentityNumber",
    "identityNumber",
    "identity_number",
)

_PROVIDER_EMPLOYEE_NO_KEYS = ("EmployeeNo", "employeeNo", "employee_no")


def normalize_national_id(value: object) -> str:
    """Return a formatting-insensitive, otherwise exact National ID key."""
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


def mask_national_id(value: object) -> str:
    normalized = normalize_national_id(value)
    if not normalized:
        return ""
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return f"{'*' * (len(normalized) - 4)}{normalized[-4:]}"


def _first_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def extract_provider_national_id(employee_details: dict[str, Any]) -> str | None:
    value = _first_value(employee_details, _PROVIDER_NATIONAL_ID_KEYS)
    normalized = normalize_national_id(value)
    return normalized or None


def extract_provider_employee_no(employee_details: dict[str, Any]) -> str:
    value = _first_value(employee_details, _PROVIDER_EMPLOYEE_NO_KEYS)
    return str(value or "").strip()


def validate_exact_provider_identity(
    *,
    loanhub_national_id: str,
    requested_employee_no: str,
    employee_details: dict[str, Any],
) -> dict[str, Any]:
    """Validate only exact identifiers; never fall back to names or DOB.

    CDAS v1.5 does not document a National ID in Employee Details. Therefore the
    National ID is the exact LoanHub borrower lookup key and EmployeeNo is the
    documented CDAS payroll key. If CDAS supplies an undocumented National ID,
    it becomes a mandatory exact-match check as an additional safety control.
    """
    normalized_loanhub_id = normalize_national_id(loanhub_national_id)
    if not normalized_loanhub_id:
        raise CdasExactIdentityError(422, "The LoanHub client must have a National ID before CDAS can be linked")

    requested = str(requested_employee_no or "").strip()
    provider_employee_no = extract_provider_employee_no(employee_details)
    if not provider_employee_no:
        raise CdasExactIdentityError(502, "CDAS employee details did not return an employee number")
    if provider_employee_no.casefold() != requested.casefold():
        raise CdasExactIdentityError(409, "CDAS returned a different employee number than the one searched")

    provider_national_id = extract_provider_national_id(employee_details)
    if provider_national_id and provider_national_id != normalized_loanhub_id:
        raise CdasExactIdentityError(409, "The National ID returned by CDAS does not match the LoanHub client")

    return {
        "basis": (
            "EXACT_NATIONAL_ID_AND_CDAS_EMPLOYEE_NO"
            if provider_national_id
            else "EXACT_LOANHUB_NATIONAL_ID_PLUS_CDAS_EMPLOYEE_NO"
        ),
        "provider_national_id_present": provider_national_id is not None,
        "provider_employee_no": provider_employee_no,
        "national_id_masked": mask_national_id(normalized_loanhub_id),
    }


def resolve_company_borrower_by_national_id(
    db: Session,
    *,
    company_id: UUID,
    national_id: str,
) -> ResolvedCdasBorrower:
    needle = normalize_national_id(national_id)
    if not needle:
        raise CdasExactIdentityError(422, "Enter a valid National ID")

    rows = (
        db.query(Borrower, CompanyBorrowerAccount, Person)
        .join(
            CompanyBorrowerAccount,
            CompanyBorrowerAccount.borrower_id == Borrower.id,
        )
        .join(User, User.id == Borrower.user_id)
        .join(Person, Person.user_id == User.id)
        .filter(
            CompanyBorrowerAccount.company_id == company_id,
            CompanyBorrowerAccount.status == "active",
            Person.national_id.isnot(None),
        )
        .all()
    )

    matches = [
        ResolvedCdasBorrower(borrower=borrower, account=account, person=person)
        for borrower, account, person in rows
        if normalize_national_id(person.national_id) == needle
    ]
    if not matches:
        raise CdasExactIdentityError(404, "No active LoanHub client matches that National ID")
    if len(matches) > 1:
        raise CdasExactIdentityError(409, "More than one active LoanHub client resolves to that National ID")
    return matches[0]


def upsert_exact_verified_payroll_profile(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    branch_id: UUID | None,
    employee_no: str,
    verified_by_user_id: UUID,
    identity_metadata: dict[str, Any],
    verified_at: Any,
) -> CDASPayrollProfile:
    cleaned_employee_no = employee_no.strip()

    conflicting = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.employee_number == cleaned_employee_no,
            CDASPayrollProfile.borrower_id != borrower_id,
            CDASPayrollProfile.verified.is_(True),
        )
        .first()
    )
    if conflicting is not None:
        raise CdasExactIdentityError(409, "This CDAS employee number is already verified against another LoanHub client")

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == borrower_id,
        )
        .one_or_none()
    )
    if profile is None:
        profile = CDASPayrollProfile(
            company_id=company_id,
            borrower_id=borrower_id,
            branch_id=branch_id,
            employee_number=cleaned_employee_no,
        )
        db.add(profile)
    elif profile.employee_number.strip().casefold() != cleaned_employee_no.casefold():
        raise CdasExactIdentityError(
            409,
            "This LoanHub client already has a different CDAS employee number on the payroll profile",
        )

    profile.branch_id = branch_id
    profile.employee_number = cleaned_employee_no
    profile.verified = True
    profile.verified_at = verified_at
    profile.verified_by_user_id = verified_by_user_id
    # Keep the established reference so existing branch-scope read guards remain compatible.
    profile.verification_reference = "CDAS_API_V1_5"
    basis = str(identity_metadata.get("basis") or "EXACT_LOANHUB_NATIONAL_ID_PLUS_CDAS_EMPLOYEE_NO")
    provider_id_note = (
        "CDAS also returned a National ID and it matched exactly."
        if identity_metadata.get("provider_national_id_present")
        else "CDAS v1.5 does not document a National ID in Employee Details, so no provider National ID claim was made."
    )
    profile.verification_notes = (
        f"Exact-ID link basis: {basis}. LoanHub client was resolved by exact normalized National ID; "
        f"CDAS returned the exact requested EmployeeNo. {provider_id_note} No fuzzy name or date-of-birth matching was used."
    )
    return profile
