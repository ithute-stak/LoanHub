"""Non-routed final registration of a signed LoanContract's locked PDF.

Re-resolves the authoritative LoanContract, frozen terms, signatures and
current generated PDF immediately before committing the issuance. A staged
object may remain retained when a contract changes; never delete it or
release it as issued. Existing loan/contract generators are untouched.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import TenantContext
from services.document_issuance_contract_source import load_signed_loan_contract_pdf
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_immutable_staging import StagedLockedCandidate
from services.document_issuance_locked_registration import (
    CommittedLockedIssuance, register_locked_staged_document,
)


def register_signed_contract_locked_issuance(
    *, db: Session, context: TenantContext,
    loan_id: UUID, contract_id: UUID, contract_version: int,
    staged: StagedLockedCandidate, store: S3ObjectLockPdfStore,
    stamp_configuration_version: int, idempotency_key: str,
) -> CommittedLockedIssuance:
    """Verify signed-contract provenance again at the commit boundary.

    The staged PDF must be derived from the exact current persisted contract
    PDF version. The generic registration layer still checks stamp approval,
    exact locked S3 version and audit transaction before returning any bytes.
    """
    source = load_signed_loan_contract_pdf(
        db=db, context=context, loan_id=loan_id,
        contract_id=contract_id, contract_version=contract_version,
    )
    if source.tenant_id != context.company_id or source.contract_id != contract_id:
        raise PermissionError("Signed contract tenant and source identity mismatch")
    if (staged.candidate.tenant_id != source.tenant_id
            or staged.source_sha256_hex != source.sha256_hex):
        raise PermissionError("Signed contract PDF changed after locked staging")
    return register_locked_staged_document(
        db=db, context=context, staged=staged, store=store,
        source_pdf=source.pdf_bytes, source_type="loan_contract",
        source_id=str(contract_id), document_type="loan_contract",
        idempotency_key=idempotency_key, version=contract_version,
        stamp_configuration_version=stamp_configuration_version,
    )
