from sqlalchemy import Boolean, Column, Enum, String, Text
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import CompanyStatus, InstitutionType


class LoanCompany(Base):
    __tablename__ = "loan_companies"

    name = Column(String(200), unique=True, nullable=False)
    institution_type = Column(
        Enum(InstitutionType),
        nullable=False,
        default=InstitutionType.LOAN_COMPANY,
        index=True,
    )
    registration_number = Column(String(100), unique=True, nullable=True)
    license_number = Column(String(100), unique=True, nullable=True)

    phone = Column(String(30), nullable=False)
    email = Column(String(150), nullable=True)
    website = Column(String(200), nullable=True)

    address = Column(Text, nullable=True)
    district = Column(String(100), nullable=True)

    # The only M-Pesa setting a LoanHub tenant owns. IthutePayBridge centrally
    # manages the M-Pesa API key, platform public key, Origin and callbacks.
    # This shortcode is used as ServiceProviderCode for both money IN and OUT.
    mpesa_shortcode = Column(String(12), nullable=True, index=True)

    status = Column(
        Enum(CompanyStatus),
        nullable=False,
        default=CompanyStatus.PENDING,
    )
    is_active = Column(Boolean, nullable=False, default=False)

    governance_profile = relationship(
        "InstitutionGovernanceProfile",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    branches = relationship(
        "CompanyBranch",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    staff_members = relationship(
        "CompanyStaff",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    loan_products = relationship(
        "LoanProduct",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    offers = relationship("LoanOffer", back_populates="company")
    subscriptions = relationship(
        "CompanySubscription",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    marketplace_unlocks = relationship(
        "MarketplaceUnlock",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    payment_transactions = relationship(
        "PaymentTransaction",
        back_populates="company",
    )
    loans = relationship("ClientCompanyLoan", back_populates="company")

    @property
    def legal_name(self) -> str:
        """Canonical legal/display name exposed to external service integrations."""
        return self.name
