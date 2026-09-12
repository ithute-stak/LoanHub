from __future__ import annotations

import re
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, get_user_context
from database.models.company import LoanCompany
from database.models.company_website import CompanyWebsiteProfile
from database.models.enums import CompanyStatus
from database.models.loan_product import LoanProduct
from database.schemas.company_website import (
    CompanyWebsitePublish,
    CompanyWebsiteRead,
    CompanyWebsiteUpdate,
    PublicCompanyWebsiteRead,
    PublicLoanProductRead,
)
from database.session import get_db


router = APIRouter(prefix="/company-websites", tags=["Company Website Builder"])

_RESERVED_CODES = {
    "api",
    "borrower",
    "borrower-registration",
    "company",
    "forgot-password",
    "login",
    "platform",
    "privacy",
    "register",
    "superadmin",
}


class CompanyWebsiteReadinessCheck(BaseModel):
    key: str
    label: str
    passed: bool
    required: bool = False
    detail: str
    weight: int = Field(ge=0, le=100)


class CompanyWebsiteReadinessRead(BaseModel):
    score: int = Field(ge=0, le=100)
    ready_to_publish: bool
    active_product_count: int
    checks: list[CompanyWebsiteReadinessCheck]


def _require_company_manager(context: TenantContext) -> None:
    if not context.company_id or not context.company:
        raise HTTPException(status_code=403, detail="Select a loan company first")
    if context.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only company owners and administrators can customise the public website")


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return clean[:48] or "loan-company"


def _generate_public_code(db: Session, company: LoanCompany) -> str:
    base = _slug(company.name)
    for _ in range(20):
        candidate = f"{base}-{secrets.token_hex(3)}"
        if candidate in _RESERVED_CODES:
            continue
        exists = db.query(CompanyWebsiteProfile.id).filter(CompanyWebsiteProfile.public_code == candidate).first()
        if not exists:
            return candidate
    raise HTTPException(status_code=503, detail="Could not allocate a unique public website code")


def _profile_for_company(db: Session, company_id):
    return db.query(CompanyWebsiteProfile).filter(CompanyWebsiteProfile.company_id == company_id).first()


def _active_product_count(db: Session, company_id) -> int:
    return db.query(LoanProduct.id).filter(
        LoanProduct.company_id == company_id,
        LoanProduct.is_active.is_(True),
    ).count()


def _loan_products(db: Session, company_id) -> list[PublicLoanProductRead]:
    records = (
        db.query(LoanProduct)
        .filter(LoanProduct.company_id == company_id, LoanProduct.is_active.is_(True))
        .order_by(LoanProduct.name.asc())
        .limit(50)
        .all()
    )
    return [
        PublicLoanProductRead(
            id=record.id,
            name=record.name,
            description=record.description,
            min_amount=float(record.min_amount),
            max_amount=float(record.max_amount),
            min_term_months=record.min_term_months,
            max_term_months=record.max_term_months,
            interest_rate_percent=float(record.interest_rate_percent),
            processing_fee=float(record.processing_fee),
        )
        for record in records
    ]


def _readiness(db: Session, company: LoanCompany, profile: CompanyWebsiteProfile) -> CompanyWebsiteReadinessRead:
    product_count = _active_product_count(db, company.id)
    checks = [
        CompanyWebsiteReadinessCheck(
            key="company_active",
            label="Company account is active",
            passed=bool(company.is_active),
            required=True,
            detail="The company must be active before its public website can be published.",
            weight=15,
        ),
        CompanyWebsiteReadinessCheck(
            key="company_approved",
            label="Company registration is approved",
            passed=company.status == CompanyStatus.APPROVED,
            required=True,
            detail="Only an approved lender/company can expose a LoanHub public website.",
            weight=20,
        ),
        CompanyWebsiteReadinessCheck(
            key="headline",
            label="Clear public headline",
            passed=bool((profile.headline or "").strip()),
            required=True,
            detail="Add a clear headline that tells visitors what the company offers.",
            weight=15,
        ),
        CompanyWebsiteReadinessCheck(
            key="contact",
            label="Public contact channel",
            passed=bool((profile.contact_phone or company.phone or "").strip() or (profile.contact_email or company.email or "").strip()),
            required=True,
            detail="Visitors need at least a phone number or email address to contact the company.",
            weight=15,
        ),
        CompanyWebsiteReadinessCheck(
            key="about",
            label="Company introduction",
            passed=len((profile.about or "").strip()) >= 40,
            detail="A useful About section improves trust and gives visitors context.",
            weight=10,
        ),
        CompanyWebsiteReadinessCheck(
            key="branding",
            label="Brand colours are configured",
            passed=bool(profile.primary_color and profile.accent_color),
            detail="Primary and accent colours keep the public experience aligned with the company brand.",
            weight=10,
        ),
        CompanyWebsiteReadinessCheck(
            key="products",
            label="Loan products are ready",
            passed=(not profile.show_loan_products) or product_count > 0,
            detail=(
                "At least one active loan product is needed while the loan-product section is enabled."
                if profile.show_loan_products
                else "The loan-product section is intentionally hidden."
            ),
            weight=10,
        ),
        CompanyWebsiteReadinessCheck(
            key="cta",
            label="Visitor next step is enabled",
            passed=bool(profile.show_account_cta or (profile.contact_phone or profile.contact_email or company.phone or company.email)),
            detail="Keep an account call-to-action enabled or provide a direct contact route.",
            weight=5,
        ),
    ]
    score = sum(check.weight for check in checks if check.passed)
    required_ready = all(check.passed for check in checks if check.required)
    return CompanyWebsiteReadinessRead(
        score=score,
        ready_to_publish=required_ready,
        active_product_count=product_count,
        checks=checks,
    )


def _public_payload(db: Session, profile: CompanyWebsiteProfile) -> PublicCompanyWebsiteRead:
    company = profile.company
    products = _loan_products(db, company.id) if profile.show_loan_products else []
    return PublicCompanyWebsiteRead(
        public_code=profile.public_code,
        company_name=company.name,
        registration_number=company.registration_number,
        license_number=company.license_number,
        company_phone=company.phone,
        company_email=company.email,
        company_address=company.address,
        company_district=company.district,
        template_key=profile.template_key,
        headline=profile.headline,
        subheadline=profile.subheadline,
        about=profile.about,
        primary_color=profile.primary_color,
        accent_color=profile.accent_color,
        hero_badge=profile.hero_badge,
        contact_phone=profile.contact_phone or company.phone,
        contact_email=profile.contact_email or company.email,
        show_loan_products=profile.show_loan_products,
        show_account_cta=profile.show_account_cta,
        custom_sections=profile.custom_sections or [],
        loan_products=products,
    )


def _start_profile(db: Session, context: TenantContext) -> CompanyWebsiteProfile:
    _require_company_manager(context)
    existing = _profile_for_company(db, context.company_id)
    if existing:
        return existing
    company = context.company
    profile = CompanyWebsiteProfile(
        company_id=context.company_id,
        public_code=_generate_public_code(db, company),
        template_key="trust_community",
        is_published=False,
        headline=f"Simple, responsible loans from {company.name}",
        subheadline="Explore available loan products, create your LoanHub borrower account and manage your lending journey securely online.",
        about=f"{company.name} uses LoanHub to provide a transparent and secure digital lending experience.",
        primary_color="#0F4C81",
        accent_color="#16A34A",
        hero_badge="Powered securely by LoanHub",
        contact_phone=company.phone,
        contact_email=company.email,
        show_loan_products=True,
        show_account_cta=True,
        custom_sections=[],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/mine", response_model=CompanyWebsiteRead | None)
def get_my_company_website(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _require_company_manager(context)
    return _profile_for_company(db, context.company_id)


@router.get("/readiness", response_model=CompanyWebsiteReadinessRead)
def get_company_website_readiness(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _require_company_manager(context)
    profile = _profile_for_company(db, context.company_id)
    if not profile:
        profile = _start_profile(db, context)
    return _readiness(db, context.company, profile)


@router.get("/loan-products", response_model=list[PublicLoanProductRead])
def get_company_website_loan_products(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _require_company_manager(context)
    return _loan_products(db, context.company_id)


@router.post("/start", response_model=CompanyWebsiteRead, status_code=status.HTTP_201_CREATED)
def start_company_website(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    return _start_profile(db, context)


@router.patch("/mine", response_model=CompanyWebsiteRead)
def update_company_website(
    payload: CompanyWebsiteUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _require_company_manager(context)
    profile = _profile_for_company(db, context.company_id)
    if not profile:
        profile = _start_profile(db, context)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/publish", response_model=CompanyWebsiteRead)
def publish_company_website(
    payload: CompanyWebsitePublish,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _require_company_manager(context)
    profile = _profile_for_company(db, context.company_id)
    if not profile:
        profile = _start_profile(db, context)
    if payload.is_published:
        readiness = _readiness(db, context.company, profile)
        if not readiness.ready_to_publish:
            missing = [check.label for check in readiness.checks if check.required and not check.passed]
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Website is not ready to publish. Complete: {', '.join(missing)}.",
            )
    profile.is_published = payload.is_published
    profile.published_at = datetime.utcnow() if payload.is_published else None
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/public/{public_code}", response_model=PublicCompanyWebsiteRead)
def get_public_company_website(public_code: str, db: Session = Depends(get_db)):
    profile = (
        db.query(CompanyWebsiteProfile)
        .join(LoanCompany, LoanCompany.id == CompanyWebsiteProfile.company_id)
        .filter(
            CompanyWebsiteProfile.public_code == public_code.lower().strip(),
            CompanyWebsiteProfile.is_published.is_(True),
            LoanCompany.is_active.is_(True),
            LoanCompany.status == CompanyStatus.APPROVED,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Public loan website not found")
    return _public_payload(db, profile)