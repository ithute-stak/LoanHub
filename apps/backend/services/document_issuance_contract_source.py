"""Non-routed source adapter for LoanHub's real signed credit agreements.

Unlike user supplied ManagedFile links, this resolves the current PDF through
LoanContract.pdf_file_id and verifies the frozen terms hash and signed state.
No contract generation, mutation, public route or issuance occurs here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.models.file_management import ManagedFile
from database.models.origination import LoanContract
from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_loan_source import require_authorized_loan_document_record
from services.file_service import read_file_bytes


@dataclass(frozen=True)
class VerifiedSignedContractPdf:
    tenant_id: UUID
    loan_id: UUID
    contract_id: UUID
    contract_version: int
    file_id: UUID
    pdf_bytes: bytes
    sha256_hex: str
    terms_sha256_hex: str


def load_signed_loan_contract_pdf(
    *, db: Session, context: TenantContext, loan_id: UUID,
    contract_id: UUID, contract_version: int,
) -> VerifiedSignedContractPdf:
    """Load an actual signed LoanContract's current, scanner-clean PDF only."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (context.is_platform_admin or not isinstance(context.company_id, UUID)
            or context.company is None or context.company.id != context.company_id
            or context.user is None or context.staff is None
            or not isinstance(loan_id, UUID) or not isinstance(contract_id, UUID)):
        raise PermissionError("Verified tenant, loan and contract required")
    if type(contract_version) is not int or contract_version < 1:
        raise ValueError("Positive contract version required")
    loan = require_authorized_loan_document_record(
        db=db, context=context, loan_id=loan_id,
    )
    contract = db.query(LoanContract).filter(
        LoanContract.id == contract_id,
        LoanContract.company_id == context.company_id,
        LoanContract.loan_id == loan_id,
        LoanContract.borrower_id == loan.borrower_id,
        LoanContract.version == contract_version,
        LoanContract.status == "signed",
        LoanContract.locked_at.isnot(None),
        LoanContract.pdf_file_id.isnot(None),
    ).one_or_none()
    if (contract is None or contract.id != contract_id
            or contract.loan_id != loan_id
            or contract.company_id != context.company_id
            or contract.borrower_id != loan.borrower_id
            or contract.version != contract_version
            or contract.status != "signed" or contract.locked_at is None
            or contract.borrower_signed_at is None
            or contract.company_signed_at is None
            or not isinstance(contract.pdf_file_id, UUID)):
        raise PermissionError("Current fully signed tenant loan contract required")

    terms = contract.terms_snapshot
    if not isinstance(terms, dict) or not terms:
        raise PermissionError("Frozen contract terms required")
    canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"), default=str)
    terms_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if contract.contract_hash != terms_digest:
        raise PermissionError("Loan contract terms hash mismatch")

    source = db.query(ManagedFile).filter(
        ManagedFile.id == contract.pdf_file_id,
        ManagedFile.company_id == context.company_id,
        ManagedFile.linked_entity_type == "loan_contract",
        ManagedFile.linked_entity_id == str(contract.id),
        ManagedFile.category == "loan_contract",
        ManagedFile.is_deleted.is_(False),
        ManagedFile.is_confidential.is_(True),
        ManagedFile.visibility == "company",
        ManagedFile.scan_status == "clean",
        ManagedFile.mime_type == "application/pdf",
    ).one_or_none()
    if (source is None or source.id != contract.pdf_file_id
            or source.company_id != context.company_id
            or source.linked_entity_type != "loan_contract"
            or source.linked_entity_id != str(contract.id)
            or source.category != "loan_contract"
            or source.is_deleted is not False
            or source.is_confidential is not True
            or source.visibility != "company"
            or source.scan_status != "clean"
            or source.mime_type != "application/pdf"):
        raise PermissionError("Current signed contract PDF is unavailable or untrusted")
    pdf = read_file_bytes(source)
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
        raise PermissionError("Contract PDF bytes invalid")
    digest = pdf_fingerprint(pdf)
    if digest != source.checksum_sha256:
        raise PermissionError("Current contract PDF fingerprint mismatch")
    return VerifiedSignedContractPdf(
        tenant_id=context.company_id, loan_id=loan_id,
        contract_id=contract.id, contract_version=contract.version,
        file_id=source.id, pdf_bytes=pdf, sha256_hex=digest,
        terms_sha256_hex=terms_digest,
    )


def stage_signed_loan_contract_pdf(
    *, db: Session, context: TenantContext, loan_id: UUID,
    contract_id: UUID, contract_version: int,
    trusted_verification_origin: str, store, stamp_configuration_version: int,
):
    """Non-routed; stage verified current signed contract through approved pipeline."""
    from services.document_issuance_immutable_staging import stage_locked_document_candidate

    source = load_signed_loan_contract_pdf(
        db=db, context=context, loan_id=loan_id,
        contract_id=contract_id, contract_version=contract_version,
    )
    return stage_locked_document_candidate(
        context=context, source_pdf=source.pdf_bytes,
        trusted_verification_origin=trusted_verification_origin, store=store,
        db=db, stamp_configuration_version=stamp_configuration_version,
    )
