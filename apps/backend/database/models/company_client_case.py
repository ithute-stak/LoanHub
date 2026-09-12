from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyClientCaseEntry(Base):
    """Internal company note/legal-action history for a borrower account.

    Entries are tenant-owned and deliberately separate from the borrower identity
    so one lending company cannot see another company's collections/legal notes.
    """

    __tablename__ = "company_client_case_entries"
    __table_args__ = (
        Index(
            "ix_company_client_case_entries_company_account_created",
            "company_id",
            "company_borrower_account_id",
            "created_at",
        ),
        Index(
            "ix_company_client_case_entries_company_type_status",
            "company_id",
            "entry_type",
            "status",
        ),
    )

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
        ForeignKey("borrowers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entry_type = Column(String(30), nullable=False, index=True)
    category = Column(String(60), nullable=False, default="general", index=True)
    title = Column(String(180), nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, default="recorded", index=True)
    action_date = Column(DateTime(timezone=True), nullable=True, index=True)
    reference_number = Column(String(180), nullable=True)
    amount = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    account = relationship("CompanyBorrowerAccount")
    borrower = relationship("Borrower")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
