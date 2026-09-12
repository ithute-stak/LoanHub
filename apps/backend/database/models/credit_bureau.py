from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class CreditBureauProviderPayload(Base):
    """Encrypted provider-only payload linked to LoanHub's existing bureau enquiry.

    LoanHub already has `CreditBureauEnquiry` in `lending_operations.py`.  This
    companion table deliberately keeps the full provider response outside that
    generic record because the generic Lending Operations API exposes
    `response_data`.  Only normalized, non-secret bureau facts belong there;
    the complete Experian body remains encrypted here for controlled audit.
    """

    __tablename__ = "credit_bureau_provider_payloads"
    __table_args__ = (
        UniqueConstraint("enquiry_id", name="uq_credit_bureau_provider_payload_enquiry"),
    )

    enquiry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credit_bureau_enquiries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(80), nullable=False, default="experian", index=True)
    raw_response_encrypted = Column(Text, nullable=False)
