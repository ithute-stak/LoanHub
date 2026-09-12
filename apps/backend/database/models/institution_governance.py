from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class InstitutionGovernanceProfile(Base):
    """Regulatory, privacy, interoperability and responsible-AI controls per tenant."""

    __tablename__ = "institution_governance_profiles"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    regulator_name = Column(String(200), nullable=True)
    regulatory_license_category = Column(String(160), nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    bank_code = Column(String(40), nullable=True)
    swift_bic = Column(String(20), nullable=True)

    aml_cft_officer_name = Column(String(200), nullable=True)
    aml_cft_officer_email = Column(String(200), nullable=True)
    data_protection_officer_name = Column(String(200), nullable=True)
    data_protection_officer_email = Column(String(200), nullable=True)
    regulatory_reporting_contact_email = Column(String(200), nullable=True)
    complaints_contact = Column(String(200), nullable=True)

    privacy_notice_url = Column(String(500), nullable=True)
    data_retention_months = Column(Integer, nullable=False, default=60)
    consent_management_enabled = Column(Boolean, nullable=False, default=False)
    data_export_enabled = Column(Boolean, nullable=False, default=False)

    ai_decisioning_enabled = Column(Boolean, nullable=False, default=False)
    ai_human_review_required = Column(Boolean, nullable=False, default=True)
    ai_explainability_required = Column(Boolean, nullable=False, default=True)
    ai_bias_monitoring_enabled = Column(Boolean, nullable=False, default=False)

    govstack_interoperability_status = Column(
        String(40),
        nullable=False,
        default="not_started",
    )
    dpg_readiness_status = Column(
        String(40),
        nullable=False,
        default="not_started",
    )
    open_api_published = Column(Boolean, nullable=False, default=False)
    low_bandwidth_supported = Column(Boolean, nullable=False, default=False)
    accessibility_reviewed = Column(Boolean, nullable=False, default=False)
    english_sesotho_supported = Column(Boolean, nullable=False, default=False)
    business_continuity_tested = Column(Boolean, nullable=False, default=False)
    incident_response_tested = Column(Boolean, nullable=False, default=False)
    interoperability_notes = Column(Text, nullable=True)

    company = relationship("LoanCompany", back_populates="governance_profile")
