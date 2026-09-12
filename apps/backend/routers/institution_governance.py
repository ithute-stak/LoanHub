from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.audit_log import AuditLog
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import InstitutionType, UserRole
from database.models.institution_governance import InstitutionGovernanceProfile
from database.schemas.institution_governance import (
    GovStackCapabilityRead,
    InstitutionGovernanceProfileRead,
    InstitutionGovernanceProfileUpdate,
    InstitutionReadinessRead,
    InstitutionRoleRead,
    ReadinessControlRead,
)
from database.session import get_db


router = APIRouter(
    prefix="/institution-governance",
    tags=["Institution Governance"],
)

NON_NULLABLE_PROFILE_FIELDS = {
    "data_retention_months",
    "consent_management_enabled",
    "data_export_enabled",
    "ai_decisioning_enabled",
    "ai_human_review_required",
    "ai_explainability_required",
    "ai_bias_monitoring_enabled",
    "govstack_interoperability_status",
    "dpg_readiness_status",
    "open_api_published",
    "low_bandwidth_supported",
    "accessibility_reviewed",
    "english_sesotho_supported",
    "business_continuity_tested",
    "incident_response_tested",
}
EMAIL_PROFILE_FIELDS = {
    "aml_cft_officer_email",
    "data_protection_officer_email",
    "regulatory_reporting_contact_email",
}

GOVERNANCE_WRITE_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.RISK_MANAGER,
    UserRole.AML_CFT_OFFICER,
    UserRole.DATA_PROTECTION_OFFICER,
    UserRole.REGULATORY_REPORTING_OFFICER,
    UserRole.INFORMATION_SECURITY_OFFICER,
}

ROLE_CATALOG = [
    (UserRole.COMPANY_OWNER, "Institution owner / board representative", "institution", "Ultimate tenant ownership and board accountability"),
    (UserRole.COMPANY_ADMIN, "Institution administrator", "institution", "Tenant configuration, staff access and delegated administration"),
    (UserRole.BRANCH_MANAGER, "Branch manager", "branch", "Branch operations, staff and portfolio oversight"),
    (UserRole.OPERATIONS_OFFICER, "Operations officer", "branch", "Operational controls, service delivery and workflow coordination"),
    (UserRole.LOAN_OFFICER, "Loan officer", "branch", "Origination, customer service and loan administration"),
    (UserRole.CREDIT_ANALYST, "Credit analyst", "branch", "Affordability, credit analysis and recommendation"),
    (UserRole.RISK_MANAGER, "Risk manager", "institution", "Credit, operational and enterprise risk oversight"),
    (UserRole.FINANCE_OFFICER, "Finance officer", "institution_or_branch", "Accounting, payments and financial control"),
    (UserRole.TREASURY_OFFICER, "Treasury officer", "institution", "Liquidity, funding, cash and reconciliation oversight"),
    (UserRole.COLLECTIONS_OFFICER, "Collections officer", "branch", "Arrears management and recoveries"),
    (UserRole.COMPLIANCE_OFFICER, "Compliance officer", "institution", "Regulatory compliance and control monitoring"),
    (UserRole.AML_CFT_OFFICER, "AML/CFT officer", "institution", "Customer due diligence, screening and suspicious-activity controls"),
    (UserRole.REGULATORY_REPORTING_OFFICER, "Regulatory reporting officer", "institution", "Preparation and submission of regulator returns"),
    (UserRole.DATA_PROTECTION_OFFICER, "Data-protection officer", "institution", "Privacy, consent, retention and data-subject rights"),
    (UserRole.AUDITOR, "Internal auditor", "institution", "Independent review of controls, records and exceptions"),
    (UserRole.INFORMATION_SECURITY_OFFICER, "Information-security officer", "institution", "Cybersecurity, incidents, access and resilience controls"),
    (UserRole.CUSTOMER_SUPPORT, "Customer service / complaints officer", "branch", "Customer support, complaints and dispute handling"),
    (UserRole.HR_MANAGER, "HR manager", "institution", "Workforce records, policy and employee lifecycle"),
    (UserRole.PERFORMANCE_MANAGER, "Performance manager", "institution", "Targets, KPIs and staff performance"),
    (UserRole.IT_SUPPORT, "IT support", "institution", "Technical support, integrations and operational availability"),
]

GOVSTACK_CAPABILITIES = [
    ("registry", "Registry", "implemented", "Tenant, branch, staff, borrower, product and loan registries"),
    ("identity", "Identity", "integration_ready", "KYC and consent records; national-ID connector requires an authorised endpoint"),
    ("workflow", "Workflow", "implemented", "Versioned workflow templates and auditable workflow instances"),
    ("payment", "Payment", "implemented", "Payment ledger, proof references and provider-ready channels"),
    ("information_mediator", "Information mediator", "integration_ready", "Tenant API keys, scoped APIs and signed webhooks"),
    ("notification", "Notification", "implemented", "In-app and real-time notification building block"),
    ("reporting", "Reporting", "implemented", "Generated reports and dual-control regulatory submissions"),
    ("audit", "Audit", "implemented", "Actor, tenant, record and changed-field audit history"),
    ("responsible_ai", "Responsible AI", "implemented", "Explainability, human-review and bias-monitoring governance controls"),
]


def _company_id(context: TenantContext, requested: UUID | None) -> UUID:
    if context.is_platform_admin:
        if not requested:
            raise HTTPException(
                status_code=422,
                detail="company_id is required for platform oversight",
            )
        return requested
    if not context.company_id:
        raise HTTPException(status_code=403, detail="Select an institution tenant")
    if requested and requested != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-institution access is not allowed")
    return context.company_id


def _company(db: Session, company_id: UUID) -> LoanCompany:
    company = db.query(LoanCompany).filter(LoanCompany.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Institution not found")
    return company


def _profile(db: Session, company_id: UUID) -> InstitutionGovernanceProfile:
    profile = (
        db.query(InstitutionGovernanceProfile)
        .filter(InstitutionGovernanceProfile.company_id == company_id)
        .first()
    )
    if profile:
        return profile
    profile = InstitutionGovernanceProfile(company_id=company_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _can_write(context: TenantContext) -> bool:
    return bool(
        context.is_platform_admin
        or (context.staff and context.staff.role in GOVERNANCE_WRITE_ROLES)
    )


def _json_value(value):
    return value.isoformat() if isinstance(value, date) else value


@router.get("/roles", response_model=list[InstitutionRoleRead])
def institution_role_catalog(
    _: TenantContext = Depends(get_tenant_context),
):
    return [
        InstitutionRoleRead(role=role, label=label, scope=scope, purpose=purpose)
        for role, label, scope, purpose in ROLE_CATALOG
    ]


@router.get("/govstack-capabilities", response_model=list[GovStackCapabilityRead])
def govstack_capabilities(
    _: TenantContext = Depends(get_tenant_context),
):
    return [
        GovStackCapabilityRead(
            key=key,
            label=label,
            status=status,
            implementation=implementation,
        )
        for key, label, status, implementation in GOVSTACK_CAPABILITIES
    ]


@router.get("/profile", response_model=InstitutionGovernanceProfileRead)
def get_governance_profile(
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    selected = _company_id(context, company_id)
    _company(db, selected)
    return _profile(db, selected)


@router.put("/profile", response_model=InstitutionGovernanceProfileRead)
def update_governance_profile(
    payload: InstitutionGovernanceProfileUpdate,
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not _can_write(context):
        raise HTTPException(
            status_code=403,
            detail="This role cannot change institution governance controls",
        )
    selected = _company_id(context, company_id)
    _company(db, selected)
    profile = _profile(db, selected)
    changes = payload.model_dump(exclude_unset=True)
    invalid_nulls = sorted(
        field
        for field, value in changes.items()
        if field in NON_NULLABLE_PROFILE_FIELDS and value is None
    )
    if invalid_nulls:
        raise HTTPException(
            status_code=422,
            detail=f"These governance controls cannot be null: {', '.join(invalid_nulls)}",
        )
    for field in EMAIL_PROFILE_FIELDS:
        if field in changes and changes[field] is not None:
            changes[field] = str(changes[field]).strip().lower()
    before = {
        field: _json_value(getattr(profile, field))
        for field in changes
    }
    changed_fields = []
    for field, value in changes.items():
        if getattr(profile, field) != value:
            setattr(profile, field, value)
            changed_fields.append(field)

    if changed_fields:
        db.add(
            AuditLog(
                user_id=context.user.id,
                company_id=selected,
                action="institution.governance_profile_updated",
                table_name="institution_governance_profiles",
                entity_type="institution_governance_profile",
                record_id=profile.id,
                description="Institution governance, privacy or interoperability controls were updated.",
                actor_role=context.role.value,
                severity="warning",
                status="success",
                before_data={field: before[field] for field in changed_fields},
                after_data={
                    field: _json_value(getattr(profile, field))
                    for field in changed_fields
                },
                changed_fields=changed_fields,
            )
        )
        db.commit()
        db.refresh(profile)
    return profile


def _control(
    key: str,
    category: str,
    label: str,
    complete: bool,
    detail: str,
    *,
    required: bool = True,
    applicable: bool = True,
) -> ReadinessControlRead:
    state = "complete" if complete else "attention"
    if not applicable:
        state = "not_applicable"
    return ReadinessControlRead(
        key=key,
        category=category,
        label=label,
        state=state,
        required=required and applicable,
        detail=detail,
    )


@router.get("/readiness", response_model=InstitutionReadinessRead)
def institution_readiness(
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    selected = _company_id(context, company_id)
    company = _company(db, selected)
    profile = _profile(db, selected)
    assigned_roles = {
        row.role
        for row in db.query(CompanyStaff)
        .filter(
            CompanyStaff.company_id == selected,
            CompanyStaff.is_active.is_(True),
        )
        .all()
    }
    is_regulated = company.institution_type != InstitutionType.GOVERNMENT_LENDING_PROGRAM
    ai_enabled = profile.ai_decisioning_enabled

    controls = [
        _control("registration", "licensing", "Registration number recorded", bool(company.registration_number), "Record the legal registration reference."),
        _control("licence", "licensing", "Regulatory licence recorded", bool(company.license_number), "Record the current licence number.", applicable=is_regulated),
        _control("regulator", "licensing", "Regulator identified", bool(profile.regulator_name), "Identify the responsible regulator.", applicable=is_regulated),
        _control("licence_expiry", "licensing", "Licence expiry monitored", bool(profile.license_expiry_date), "Record the licence expiry or renewal date.", applicable=is_regulated),
        _control("aml_role", "aml_cft", "AML/CFT accountability assigned", UserRole.AML_CFT_OFFICER in assigned_roles, "Assign an active AML/CFT officer.", applicable=is_regulated),
        _control("compliance_role", "governance", "Compliance accountability assigned", UserRole.COMPLIANCE_OFFICER in assigned_roles, "Assign an active compliance officer."),
        _control("risk_role", "governance", "Risk oversight assigned", UserRole.RISK_MANAGER in assigned_roles, "Assign an active risk manager."),
        _control("audit_role", "governance", "Independent audit assigned", UserRole.AUDITOR in assigned_roles, "Assign an active internal auditor."),
        _control("reporting_role", "reporting", "Regulatory reporting assigned", UserRole.REGULATORY_REPORTING_OFFICER in assigned_roles, "Assign an active regulatory-reporting officer.", applicable=is_regulated),
        _control("dpo_role", "privacy", "Data-protection accountability assigned", UserRole.DATA_PROTECTION_OFFICER in assigned_roles, "Assign an active data-protection officer."),
        _control("security_role", "security", "Information-security accountability assigned", UserRole.INFORMATION_SECURITY_OFFICER in assigned_roles, "Assign an active information-security officer."),
        _control("privacy_notice", "privacy", "Privacy notice published", bool(profile.privacy_notice_url), "Publish and record the tenant privacy-notice URL."),
        _control("consent", "privacy", "Consent management enabled", profile.consent_management_enabled, "Enable purpose-specific consent records."),
        _control("data_export", "privacy", "Data portability enabled", profile.data_export_enabled, "Enable controlled customer data export."),
        _control("open_api", "interoperability", "OpenAPI published", profile.open_api_published, "Publish supported APIs and schemas."),
        _control("govstack", "interoperability", "GovStack mapping progressed", profile.govstack_interoperability_status in {"in_progress", "ready"}, "Complete the building-block interoperability assessment."),
        _control("dpg", "digital_public_good", "DPG assessment progressed", profile.dpg_readiness_status in {"remediation", "ready_for_review"}, "Complete DPG Standard assessment and remediation."),
        _control("accessibility", "inclusion", "Accessibility reviewed", profile.accessibility_reviewed, "Complete an accessibility review."),
        _control("localisation", "inclusion", "English and Sesotho supported", profile.english_sesotho_supported, "Provide key journeys in English and Sesotho."),
        _control("low_bandwidth", "inclusion", "Low-bandwidth operation verified", profile.low_bandwidth_supported, "Verify core journeys on constrained mobile networks."),
        _control("continuity", "resilience", "Business continuity tested", profile.business_continuity_tested, "Record a successful continuity or recovery exercise."),
        _control("incident_response", "security", "Incident response tested", profile.incident_response_tested, "Run and record an incident-response exercise."),
        _control("ai_human_review", "responsible_ai", "Human review required", profile.ai_human_review_required, "Require accountable human review for AI-supported credit decisions.", applicable=ai_enabled),
        _control("ai_explainability", "responsible_ai", "Decision explanations required", profile.ai_explainability_required, "Record reasons and disclose adverse-decision reasons.", applicable=ai_enabled),
        _control("ai_bias", "responsible_ai", "Bias monitoring enabled", profile.ai_bias_monitoring_enabled, "Monitor outcomes for unfair or discriminatory patterns.", applicable=ai_enabled),
    ]
    required = [item for item in controls if item.required]
    completed = [item for item in required if item.state == "complete"]
    recommended_roles = {
        UserRole.COMPANY_ADMIN,
        UserRole.RISK_MANAGER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AML_CFT_OFFICER,
        UserRole.DATA_PROTECTION_OFFICER,
        UserRole.REGULATORY_REPORTING_OFFICER,
        UserRole.AUDITOR,
        UserRole.INFORMATION_SECURITY_OFFICER,
    }
    if not is_regulated:
        recommended_roles -= {
            UserRole.AML_CFT_OFFICER,
            UserRole.REGULATORY_REPORTING_OFFICER,
        }

    return InstitutionReadinessRead(
        company_id=selected,
        institution_type=company.institution_type,
        score_percent=round(len(completed) * 100 / len(required)) if required else 100,
        completed_required_controls=len(completed),
        required_controls=len(required),
        controls=controls,
        assigned_roles=sorted(assigned_roles, key=lambda role: role.value),
        missing_recommended_roles=sorted(
            recommended_roles - assigned_roles,
            key=lambda role: role.value,
        ),
    )
