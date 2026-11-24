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
from services.document_issuance_contract_source import (
    StagedSignedContractPdf, load_signed_loan_contract_pdf,
)
from services.document_issuance_issuer_authorization import require_current_document_issuer
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_locked_registration import (
    CommittedLockedIssuance, register_locked_staged_document,
)


def register_signed_contract_locked_issuance(
    *, db: Session, context: TenantContext,
    loan_id: UUID, contract_id: UUID, contract_version: int,
    prepared: StagedSignedContractPdf, store: S3ObjectLockPdfStore,
    stamp_configuration_version: int, idempotency_key: str,
) -> CommittedLockedIssuance:
    """Verify signed-contract provenance again at the commit boundary.

    The staged PDF must be derived from the exact current persisted contract
    PDF version. The generic registration layer still checks stamp approval,
    exact locked S3 version and audit transaction before returning any bytes.
    """
    # Only the full source + PDF bundle emitted by the signed-contract
    # staging adapter is admissible. An unrelated staged PDF is insufficient.
    if not isinstance(prepared, StagedSignedContractPdf):
        raise PermissionError("Signed contract staging attestation required")
    attested = prepared.source
    staged = prepared.staged
    if (attested.tenant_id != context.company_id
            or attested.loan_id != loan_id or attested.contract_id != contract_id
            or attested.contract_version != contract_version):
        raise PermissionError("Staged contract identity or version mismatch")
    # Tenant context and staff membership may have changed since staging.
    # Reload the currently active issuer from the same SQL session.
    require_current_document_issuer(db=db, context=context)
    locked_transaction = db.get_transaction()
    if locked_transaction is None:
        raise PermissionError("Signed-contract issuer locks require an active transaction")
    # Load loan, contract and current PDF under transaction-held FOR SHARE NOWAIT
    # locks. A competing update fails closed, rather than racing the final commit.
    source = load_signed_loan_contract_pdf(
        db=db, context=context, loan_id=loan_id,
        contract_id=contract_id, contract_version=contract_version,
        lock_for_registration=True,
    )
    if (source.tenant_id != context.company_id or source.loan_id != loan_id
            or source.contract_id != contract_id or source.contract_version != contract_version):
        raise PermissionError("Signed contract tenant and source identity mismatch")
    if (source.file_id != attested.file_id
            or source.terms_sha256_hex != attested.terms_sha256_hex
            or source.sha256_hex != attested.sha256_hex):
        raise PermissionError("Signed contract file or frozen terms changed since staging")
    if (staged.candidate.tenant_id != source.tenant_id
            or staged.source_sha256_hex != source.sha256_hex):
        raise PermissionError("Signed contract PDF changed after locked staging")
    # Releasing the issuer/source locks between validation and registration
    # would invalidate the authoritative contract snapshot.
    if db.get_transaction() is not locked_transaction:
        raise PermissionError("Signed-contract lock transaction changed before registration")
    return register_locked_staged_document(
        db=db, context=context, staged=staged, store=store,
        source_pdf=source.pdf_bytes, source_type="loan_contract",
        source_id=str(contract_id), document_type="loan_contract",
        idempotency_key=idempotency_key, version=contract_version,
        stamp_configuration_version=stamp_configuration_version,
    )
