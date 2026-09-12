from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyWebsiteProfile(Base):
    __tablename__ = "company_website_profiles"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    public_code = Column(String(90), nullable=False, unique=True, index=True)
    template_key = Column(String(40), nullable=False, default="trust_community")
    is_published = Column(Boolean, nullable=False, default=False, index=True)

    headline = Column(String(180), nullable=False)
    subheadline = Column(Text, nullable=True)
    about = Column(Text, nullable=True)
    primary_color = Column(String(12), nullable=False, default="#0F4C81")
    accent_color = Column(String(12), nullable=False, default="#16A34A")
    hero_badge = Column(String(120), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    contact_email = Column(String(255), nullable=True)
    show_loan_products = Column(Boolean, nullable=False, default=True)
    show_account_cta = Column(Boolean, nullable=False, default=True)
    custom_sections = Column(JSONB, nullable=False, default=list)
    published_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany")

    @property
    def company_name(self) -> str:
        return self.company.name if self.company else "Loan company"
