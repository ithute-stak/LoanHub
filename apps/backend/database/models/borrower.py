from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import EmploymentStatus


class Borrower(Base):
    __tablename__ = "borrowers"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    employment_status = Column(
        Enum(EmploymentStatus),
        nullable=False,
    )
    employment_type = Column(String(50), nullable=True)
    employer_name = Column(String(200), nullable=True)
    employer_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employer_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    income_day = Column(Integer, nullable=True)
    job_title = Column(String(150), nullable=True)
    employment_start_date = Column(Date, nullable=True)

    monthly_income = Column(Numeric(12, 2), nullable=True)
    net_monthly_income = Column(Numeric(12, 2), nullable=True)
    other_monthly_income = Column(Numeric(12, 2), default=0, nullable=False)
    other_income_source = Column(String(200), nullable=True)
    salary_date = Column(String(20), nullable=True)

    monthly_living_expenses = Column(Numeric(12, 2), default=0, nullable=False)
    monthly_debt_repayments = Column(Numeric(12, 2), default=0, nullable=False)
    dependants = Column(Integer, default=0, nullable=False)
    residential_status = Column(String(40), nullable=True)
    years_at_address = Column(Integer, nullable=True)

    has_existing_loans = Column(Boolean, default=False, nullable=False)
    existing_loan_total = Column(Numeric(12, 2), default=0, nullable=False)

    bank_name = Column(String(120), nullable=True)
    account_holder_name = Column(String(200), nullable=True)
    account_last_four = Column(String(4), nullable=True)

    consent_to_share_profile = Column(Boolean, default=False, nullable=False)
    consent_to_share_documents = Column(Boolean, default=False, nullable=False)
    consent_to_credit_checks = Column(Boolean, default=False, nullable=False)

    user = relationship(
        "User",
        back_populates="borrower_profile",
    )
    employer_group = relationship(
        "EmployerGroup",
        back_populates="borrowers",
    )

    loans = relationship(
        "ClientCompanyLoan",
        back_populates="borrower",
    )

    loan_requests = relationship(
        "LoanRequest",
        back_populates="borrower",
    )

    documents = relationship(
        "BorrowerDocument",
        back_populates="borrower",
    )
    payment_transactions = relationship(
        "PaymentTransaction",
        back_populates="borrower",
    )
    contacts = relationship(
        "BorrowerContact",
        back_populates="borrower",
        cascade="all, delete-orphan",
    )
