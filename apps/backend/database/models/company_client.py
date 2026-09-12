from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyBorrowerAccount(Base):
    """A tenant-owned client record for a borrower.

    The borrower identity remains global, while this record controls the
    relationship between that borrower and one lending company. Assisted
    registrations are activated immediately. Any configured platform opening fee
    is recorded as an accrued company charge and settled outside the borrower workflow.
    """

    __tablename__ = "company_borrower_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "borrower_id",
            name="uq_company_borrower_account_company_borrower",
        ),
        UniqueConstraint("account_reference", name="uq_company_borrower_account_reference"),
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
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opened_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    account_reference = Column(String(70), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="assisted_registration")
    status = Column(String(30), nullable=False, default="pending_fee", index=True)

    opening_fee_configuration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_account_opening_fee_configurations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opening_fee_amount = Column(Numeric(15, 2), nullable=False, default=0)
    opening_fee_currency = Column(String(3), nullable=False, default="LSL")
    opening_fee_status = Column(String(30), nullable=False, default="not_required", index=True)
    opening_fee_payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        unique=True,
    )

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    borrower = relationship("Borrower")
    opened_by = relationship("User", foreign_keys=[opened_by_user_id])
    opening_fee_configuration = relationship("CompanyAccountOpeningFeeConfiguration")
    opening_fee_payment = relationship(
        "PaymentTransaction",
        foreign_keys=[opening_fee_payment_id],
        post_update=True,
    )
