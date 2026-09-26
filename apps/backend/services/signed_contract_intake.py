from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext
from database.config.config import settings
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.file_management import ManagedFile
from database.models.origination import LoanContract
from database.models.person import Person
from database.models.user import User


SIGNED_CONTRACT_CATEGORY = "borrower_signed_contract"
SIGNED_CONTRACT_REVIEW_CATEGORY = "signed_contract_review"
CLIENT_FILE_LINK_TYPE = "company_borrower_account"
MAX_BATCH_FILES = 20
MAX_OCR_PAGES = 4
MIN_TEXT_LAYER_CHARS = 80
MIN_STRONG_IDENTIFIER_CHARS = 6


@dataclass(slots=True)
class ClientIdentity:
    account_id: Any
    borrower_id: Any
    branch_id: Any
    display_name: str
    national_id: str | None = None
    contract_numbers: set[str] = field(default_factory=set)
    loan_references: set[str] = field(default_factory=set)
    application_references: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ContractMatch:
    account_id: Any | None
    branch_id: Any | None
    client_name: str | None
    status: str
    reason: str
    evidence_types: list[str]


def _compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _contains_identifier(searchable: str, value: Any) -> bool:
    token = _compact(value)
    return len(token) >= MIN_STRONG_IDENTIFIER_CHARS and token in searchable


def _visible_accounts_query(db: Session, context: TenantContext):
    if not context.company_id:
        raise HTTPException(status_code=403, detail="A company context is required")
    query = (
        db.query(CompanyBorrowerAccount, Borrower, User, Person)
        .join(Borrower, Borrower.id == CompanyBorrowerAccount.borrower_id)
        .join(User, User.id == Borrower.user_id)
        .outerjoin(Person, Person.user_id == User.id)
        .filter(CompanyBorrowerAccount.company_id == context.company_id)
    )
    if (
        context.staff
        and context.staff.role not in COMPANY_MANAGEMENT_ROLES
        and context.branch_id is not None
    ):
        query = query.filter(CompanyBorrowerAccount.branch_id == context.branch_id)
    return query


def load_client_identities(db: Session, context: TenantContext) -> dict[Any, ClientIdentity]:
    identities: dict[Any, ClientIdentity] = {}
    borrower_to_account: dict[Any, Any] = {}
    for account, borrower, _user, person in _visible_accounts_query(db, context).all():
        display_name = person.full_name if person else account.account_reference
        identity = ClientIdentity(
            account_id=account.id,
            borrower_id=borrower.id,
            branch_id=account.branch_id,
            display_name=display_name,
            national_id=(person.national_id if person else None),
        )
        identities[account.id] = identity
        borrower_to_account[borrower.id] = account.id

    if not borrower_to_account:
        return identities

    loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.company_id == context.company_id,
            ClientCompanyLoan.borrower_id.in_(list(borrower_to_account)),
        )
        .all()
    )
    for loan in loans:
        account_id = borrower_to_account.get(loan.borrower_id)
        if account_id in identities and loan.loan_reference:
            identities[account_id].loan_references.add(str(loan.loan_reference))

    contracts = (
        db.query(LoanContract)
        .filter(
            LoanContract.company_id == context.company_id,
            LoanContract.borrower_id.in_(list(borrower_to_account)),
        )
        .all()
    )
    for contract in contracts:
        account_id = borrower_to_account.get(contract.borrower_id)
        if account_id not in identities:
            continue
        identity = identities[account_id]
        if contract.contract_number:
            identity.contract_numbers.add(str(contract.contract_number))
        terms = contract.terms_snapshot if isinstance(contract.terms_snapshot, dict) else {}
        application_reference = terms.get("application_reference")
        if application_reference:
            identity.application_references.add(str(application_reference))
        loan_reference = terms.get("loan_reference")
        if loan_reference:
            identity.loan_references.add(str(loan_reference))

    return identities


def match_signed_contract(db: Session, context: TenantContext, extracted_text: str) -> ContractMatch:
    searchable = _compact(extracted_text)
    if not searchable:
        return ContractMatch(None, None, None, "review", "No readable contract text was found", [])

    identities = load_client_identities(db, context)
    account_evidence: dict[Any, set[str]] = {}

    for account_id, identity in identities.items():
        evidence: set[str] = set()
        if _contains_identifier(searchable, identity.national_id):
            evidence.add("national_id")
        if any(_contains_identifier(searchable, value) for value in identity.contract_numbers):
            evidence.add("contract_number")
        if any(_contains_identifier(searchable, value) for value in identity.loan_references):
            evidence.add("loan_reference")
        if any(_contains_identifier(searchable, value) for value in identity.application_references):
            evidence.add("application_reference")
        if evidence:
            account_evidence[account_id] = evidence

    if len(account_evidence) == 1:
        account_id, evidence = next(iter(account_evidence.items()))
        identity = identities[account_id]
        return ContractMatch(
            account_id=account_id,
            branch_id=identity.branch_id,
            client_name=identity.display_name,
            status="filed",
            reason="Strong contract identifiers resolved to one client",
            evidence_types=sorted(evidence),
        )

    if len(account_evidence) > 1:
        evidence_types = sorted({item for values in account_evidence.values() for item in values})
        return ContractMatch(
            None,
            None,
            None,
            "review",
            "Strong identifiers conflict across multiple clients",
            evidence_types,
        )

    return ContractMatch(
        None,
        None,
        None,
        "review",
        "No strong client identifier matched; a name alone is never used for automatic filing",
        [],
    )


async def read_contract_upload(upload: UploadFile) -> tuple[bytes, str, str]:
    declared_mime = (upload.content_type or "application/octet-stream").lower()
    filename = Path(upload.filename or "signed-contract").name
    maximum_mb = max(1, int(settings.FILE_MAX_UPLOAD_MB))
    maximum = maximum_mb * 1024 * 1024
    content = bytearray()
    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > maximum:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {maximum_mb} MB limit",
                )
    finally:
        await upload.close()
    return bytes(content), filename, declared_mime


def checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def find_existing_intake_file(db: Session, company_id: Any, digest: str) -> ManagedFile | None:
    return (
        db.query(ManagedFile)
        .filter(
            ManagedFile.company_id == company_id,
            ManagedFile.checksum_sha256 == digest,
            ManagedFile.category.in_([SIGNED_CONTRACT_CATEGORY, SIGNED_CONTRACT_REVIEW_CATEGORY]),
            ManagedFile.is_deleted.is_(False),
        )
        .order_by(ManagedFile.created_at.desc())
        .first()
    )


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = reader.pages[:MAX_OCR_PAGES]
        return "\n".join((page.extract_text() or "") for page in pages).strip()
    except Exception:
        return ""


def _run_tesseract(image_path: Path) -> str:
    executable = shutil.which("tesseract")
    if not executable:
        return ""
    try:
        result = subprocess.run(
            [executable, str(image_path), "stdout", "-l", "eng", "--psm", "6"],
            check=True,
            capture_output=True,
            text=True,
            timeout=25,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return result.stdout.strip()


def _ocr_pdf(content: bytes) -> str:
    converter = shutil.which("pdftoppm")
    if not converter or not shutil.which("tesseract"):
        return ""
    with tempfile.TemporaryDirectory(prefix="loanhub-contract-ocr-") as directory:
        root = Path(directory)
        pdf_path = root / "contract.pdf"
        output_prefix = root / "page"
        pdf_path.write_bytes(content)
        try:
            subprocess.run(
                [
                    converter,
                    "-f",
                    "1",
                    "-l",
                    str(MAX_OCR_PAGES),
                    "-r",
                    "160",
                    "-jpeg",
                    str(pdf_path),
                    str(output_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=35,
            )
        except (subprocess.SubprocessError, OSError):
            return ""
        text_parts = [_run_tesseract(path) for path in sorted(root.glob("page-*.jpg"))]
        return "\n".join(part for part in text_parts if part).strip()


def _ocr_image(content: bytes, mime_type: str) -> str:
    suffix_by_mime = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    suffix = suffix_by_mime.get(mime_type, ".img")
    with tempfile.TemporaryDirectory(prefix="loanhub-contract-ocr-") as directory:
        path = Path(directory) / f"contract{suffix}"
        path.write_bytes(content)
        return _run_tesseract(path)


def extract_contract_text(content: bytes, mime_type: str) -> tuple[str, str]:
    if mime_type == "application/pdf":
        text = _extract_pdf_text(content)
        if len(_compact(text)) >= MIN_TEXT_LAYER_CHARS:
            return text, "pdf_text"
        ocr_text = _ocr_pdf(content)
        if ocr_text:
            return ocr_text, "local_ocr"
        return text, "pdf_text_sparse" if text else "unreadable"
    if mime_type in {"image/jpeg", "image/png", "image/webp"}:
        text = _ocr_image(content, mime_type)
        return (text, "local_ocr") if text else ("", "unreadable")
    return "", "unsupported_for_contract_reading"


def review_description(reason: str, extraction_method: str) -> str:
    return f"Signed Contracts · Needs review · {reason} · reader={extraction_method}"[:600]


def filed_description(extraction_method: str, evidence_types: list[str]) -> str:
    evidence = ", ".join(evidence_types) if evidence_types else "strong identifier"
    return (
        f"Signed Contracts · Auto-filed from global intake · matched by {evidence} · "
        f"reader={extraction_method}"
    )[:600]
