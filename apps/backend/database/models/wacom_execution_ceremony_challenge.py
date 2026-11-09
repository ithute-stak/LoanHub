"""Persist a non-operative, single-use Wacom signing-ceremony challenge.

A record can only be created as 'pending'. It is NOT proof of borrower consent,
hardware authentication, legal execution or a digital signature. No endpoint
currently issues these challenges or consumes them.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomExecutionCeremonyChallenge(Base):
    __tablename__ = "wacom_execution_ceremony_challenges"
    __table_args__ = (
        UniqueConstraint("company_id", "contract_id", name="uq_wacom_ceremony_company_contract"),
        UniqueConstraint("authorization_id", name="uq_wacom_ceremony_authorization"),
        UniqueConstraint("receipt_id", name="uq_wacom_ceremony_receipt"),
        UniqueConstraint("challenge_sha256", name="uq_wacom_ceremony_challenge_digest"),
        CheckConstraint(
            "status IN ('pending','expired','cancelled','verified','consumed')",
            name="ck_wacom_ceremony_status",
        ),
        CheckConstraint(
            "length(challenge_sha256) = 64 AND length(candidate_sha256) = 64 "
            "AND length(field_binding_sha256) = 64",
            name="ck_wacom_ceremony_hash_lengths",
        ),
        CheckConstraint(
            "(status = 'pending' AND verified_at IS NULL AND consumed_at IS NULL) OR "
            "(status IN ('expired','cancelled') AND consumed_at IS NULL) OR "
            "(status = 'verified' AND verified_at IS NOT NULL AND consumed_at IS NULL) OR "
            "(status = 'consumed' AND verified_at IS NOT NULL AND consumed_at IS NOT NULL)",
            name="ck_wacom_ceremony_state_evidence",
        ),
        CheckConstraint(
            "(workstation_proof_at IS NULL AND workstation_proof_by IS NULL AND "
            "workstation_proof_sha256 IS NULL) OR "
            "(workstation_proof_at IS NOT NULL AND workstation_proof_by IS NOT NULL "
            "AND length(workstation_proof_sha256) = 64)",
            name="ck_wacom_ceremony_workstation_proof_complete",
        ),
        CheckConstraint(
            "(borrower_affirmed_at IS NULL AND borrower_affirmed_user_id IS NULL AND "
            "borrower_affirmation_sha256 IS NULL) OR "
            "(borrower_affirmed_at IS NOT NULL AND borrower_affirmed_user_id IS NOT NULL "
            "AND length(borrower_affirmation_sha256) = 64)",
            name="ck_wacom_ceremony_borrower_affirmation_complete",
        ),
        Index("ix_wacom_ceremony_company_status", "company_id", "status"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False)
    authorization_id = Column(UUID(as_uuid=True), ForeignKey("wacom_execution_authorizations.id", ondelete="RESTRICT"), nullable=False)
    receipt_id = Column(UUID(as_uuid=True), ForeignKey("wacom_execution_receipts.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    challenge_sha256 = Column(String(64), nullable=False)
    candidate_sha256 = Column(String(64), nullable=False)
    field_binding_sha256 = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True))
    consumed_at = Column(DateTime(timezone=True))
    # Workstation-key possession ONLY; never equate with physical pen or borrower consent.
    workstation_proof_at = Column(DateTime(timezone=True))
    workstation_proof_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    workstation_proof_sha256 = Column(String(64))
    # An explicit action by the authenticated borrower's LoanHub account.
    # This is not independently verified physical STU-540 pen evidence.
    borrower_affirmed_at = Column(DateTime(timezone=True))
    borrower_affirmed_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    borrower_affirmation_sha256 = Column(String(64))
