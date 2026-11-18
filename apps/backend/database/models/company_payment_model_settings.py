"""Dedicated company payment-model settings; independent of loan calculator."""
from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class CompanyPaymentModelSettings(Base):
    __tablename__ = "company_payment_model_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_payment_model_settings_company"),
    )

    company_id = Column(
        UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    default_model = Column(String(30), nullable=False, default="existing", server_default="existing")
    allow_new_loans = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_live_collections = Column(Boolean, nullable=False, default=False, server_default="false")
