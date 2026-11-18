"""Dedicated company payment-model settings; independent of loan calculator."""
from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class CompanyPaymentModelSettings(Base):
    __tablename__ = "company_payment_model_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_payment_model_settings_company"),
        CheckConstraint("default_model IN ('existing', 'principal_x')", name="ck_company_payment_model_allowed"),
        CheckConstraint("NOT enable_live_collections OR allow_new_loans", name="ck_company_payment_model_live_requires_opt_in"),
        CheckConstraint("NOT enable_live_collections OR default_model = 'principal_x'", name="ck_company_payment_model_live_requires_default"),
    )

    company_id = Column(
        UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    default_model = Column(String(30), nullable=False, default="existing", server_default="existing")
    allow_new_loans = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_live_collections = Column(Boolean, nullable=False, default=False, server_default="false")
