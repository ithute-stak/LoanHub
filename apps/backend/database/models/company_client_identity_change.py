from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyClientIdentityChangeRequest(Base):
    """Dual-approval request for changing a borrower's global National ID.

    A company user may request a change, but the stored identity is updated only
    after the borrower (the identity owner) and a COMPANY_OWNER both approve it.
    """

    __tablename__ = "company_client_identity_change_requests"

    reference = Column(String(40), nullable=False, unique=True, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_borrower_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_borrower_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    current_national_id = Column(String(50), nullable=True)
    proposed_national_id = Column(String(50), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    borrower_approved_at = Column(DateTime(timezone=True), nullable=True)
    borrower_approved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_owner_approved_at = Column(DateTime(timezone=True), nullable=True)
    company_owner_approved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_by_role = Column(String(40), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    applied_at = Column(DateTime(timezone=True), nullable=True)
    applied_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    account = relationship("CompanyBorrowerAccount")
    borrower = relationship("Borrower")
    person = relationship("Person")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    borrower_approved_by = relationship("User", foreign_keys=[borrower_approved_by_user_id])
    company_owner_approved_by = relationship("User", foreign_keys=[company_owner_approved_by_user_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_user_id])
    applied_by = relationship("User", foreign_keys=[applied_by_user_id])
