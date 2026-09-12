import secrets
import string
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_current_active_user,
    get_user_context,
    require_platform_admin,
    require_platform_owner,
)
from core.security import hash_password
from database.models.audit_log import AuditLog
from database.models.branch import CompanyBranch
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.file_management import ManagedFile
from database.models.company_staff import CompanyStaff
from database.models.employee import EmployeeProfile
from database.models.enums import CompanyStatus, NotificationType, UserRole
from database.models.lender_access import LenderAccessRequest
from database.models.loan_offer import LoanOffer
from database.models.loan_product import LoanProduct
from database.models.marketplace_access import MarketplaceUnlock
from database.models.payment import PaymentTransaction
from database.models.notification import Notification
from database.models.subscription import CompanySubscription
from database.models.user import RefreshToken, User
from database.schemas.company import (
    CompanyBrandingRead,
    CompanyBrandingUploadRead,
    CompanyOwnerAccountRead,
    CompanyOwnerAccountUpdate,
    CompanyOwnerTemporaryPasswordRead,
    LoanCompanyCreate,
    LoanCompanyRead,
    LoanCompanyUpdate,
)
from database.session import get_db
from services.document_branding_service import (
    company_branding_payload,
    resolve_company_document_logo,
)
from services.file_service import save_upload


router = APIRouter(prefix="/companies", tags=["Loan Companies"])

def count_company_records(
    db: Session,
    model,
    company_id: UUID,
) -> int:
    return (
        db.query(func.count(model.id))
        .filter(model.company_id == company_id)
        .scalar()
        or 0
    )


def get_company_dependency_counts(
    db: Session,
    company_id: UUID,
) -> dict[str, int]:
    return {
        "staff": count_company_records(
            db,
            CompanyStaff,
            company_id,
        ),
        "branches": count_company_records(
            db,
            CompanyBranch,
            company_id,
        ),
        "loan_products": count_company_records(
            db,
            LoanProduct,
            company_id,
        ),
        "loan_offers": count_company_records(
            db,
            LoanOffer,
            company_id,
        ),
        "loans": count_company_records(
            db,
            ClientCompanyLoan,
            company_id,
        ),
        "payments": count_company_records(
            db,
            PaymentTransaction,
            company_id,
        ),
        "subscriptions": count_company_records(
            db,
            CompanySubscription,
            company_id,
        ),
        "marketplace_unlocks": count_company_records(
            db,
            MarketplaceUnlock,
            company_id,
        ),
        "marketplace_access_requests": count_company_records(
            db,
            LenderAccessRequest,
            company_id,
        ),
    }


def company_or_404(db: Session, company_id: UUID) -> LoanCompany:
    company = db.query(LoanCompany).filter(LoanCompany.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def membership_for(db: Session, user_id: UUID, company_id: UUID) -> CompanyStaff | None:
    return (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.user_id == user_id,
            CompanyStaff.company_id == company_id,
            CompanyStaff.is_active.is_(True),
        )
        .first()
    )


def company_owner_membership_or_404(db: Session, company_id: UUID) -> CompanyStaff:
    membership = (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.company_id == company_id,
            CompanyStaff.role == UserRole.COMPANY_OWNER,
            CompanyStaff.is_active.is_(True),
        )
        .order_by(
            CompanyStaff.is_primary.desc(),
            CompanyStaff.created_at.asc(),
        )
        .first()
    )
    if not membership or not membership.user:
        raise HTTPException(status_code=404, detail="No active company-owner account was found")
    return membership


def company_owner_account_response(membership: CompanyStaff) -> CompanyOwnerAccountRead:
    owner = membership.user
    full_name = (
        owner.person.full_name
        if owner.person and owner.person.full_name
        else owner.email or owner.phone
    )
    return CompanyOwnerAccountRead(
        staff_id=membership.id,
        user_id=owner.id,
        full_name=full_name,
        email=owner.email,
        phone=owner.phone,
        is_active=owner.is_active,
        is_verified=owner.is_verified,
        must_change_password=owner.must_change_password,
    )


def generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(character.islower() for character in password)
            and any(character.isupper() for character in password)
            and any(character.isdigit() for character in password)
        ):
            return password


def revoke_user_sessions(db: Session, user_id: UUID) -> None:
    (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        .update({"revoked": True}, synchronize_session=False)
    )


def record_platform_owner_account_change(
    db: Session,
    *,
    admin: User,
    owner: User,
    company_id: UUID,
    action: str,
    description: str,
    changed_fields: list[str],
    before_data: dict,
    after_data: dict,
) -> None:
    db.add(
        AuditLog(
            user_id=admin.id,
            company_id=company_id,
            action=action,
            table_name="users",
            entity_type="company_owner_account",
            record_id=owner.id,
            description=description,
            actor_role=admin.role.value,
            severity="warning",
            status="success",
            before_data=before_data,
            after_data=after_data,
            changed_fields=changed_fields,
            event_data={"target_user_id": str(owner.id), "sessions_revoked": True},
        )
    )


def assert_can_manage_company(db: Session, user: User, company_id: UUID) -> None:
    if user.role == UserRole.SUPERADMIN:
        return
    membership = membership_for(db, user.id, company_id)
    if not membership or membership.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Company owner or administrator permission is required")




def _branding_file_response(file: ManagedFile | None) -> ManagedFile | None:
    return file


def _branding_response(db: Session, company: LoanCompany, message: str | None = None) -> CompanyBrandingUploadRead:
    data = company_branding_payload(db, company)
    left = db.get(ManagedFile, data["left_logo_file_id"]) if data.get("left_logo_file_id") else None
    right = db.get(ManagedFile, data["right_logo_file_id"]) if data.get("right_logo_file_id") else None
    return CompanyBrandingUploadRead(
        company_id=company.id,
        left_logo_file=left,
        right_logo_file=right,
        left_logo_download_url=data.get("left_logo_download_url"),
        right_logo_download_url=data.get("right_logo_download_url"),
        message=message,
    )


@router.post("/", response_model=LoanCompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: LoanCompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    company = LoanCompany(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/", response_model=list[LoanCompanyRead])
def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(LoanCompany)

    if current_user.role == UserRole.SUPERADMIN:
        pass
    elif current_user.role == UserRole.BORROWER:
        query = query.filter(
            LoanCompany.status == CompanyStatus.APPROVED,
            LoanCompany.is_active.is_(True),
        )
    else:
        company_ids = (
            db.query(CompanyStaff.company_id)
            .filter(
                CompanyStaff.user_id == current_user.id,
                CompanyStaff.is_active.is_(True),
            )
            .subquery()
        )
        query = query.filter(LoanCompany.id.in_(company_ids))

    return query.order_by(LoanCompany.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{company_id}", response_model=LoanCompanyRead)
def get_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = company_or_404(db, company_id)

    if current_user.role == UserRole.SUPERADMIN:
        return company
    if current_user.role == UserRole.BORROWER:
        if company.status != CompanyStatus.APPROVED or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")
        return company
    if not membership_for(db, current_user.id, company_id):
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    return company


@router.get("/{company_id}/owner-account", response_model=CompanyOwnerAccountRead)
def get_company_owner_account(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    company_or_404(db, company_id)
    membership = company_owner_membership_or_404(db, company_id)
    return company_owner_account_response(membership)


@router.patch("/{company_id}/owner-account", response_model=CompanyOwnerAccountRead)
def update_company_owner_account(
    company_id: UUID,
    payload: CompanyOwnerAccountUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_owner),
):
    company = company_or_404(db, company_id)
    membership = company_owner_membership_or_404(db, company_id)
    owner = membership.user
    changes = payload.model_dump(exclude_unset=True)
    if "phone" in changes:
        if changes["phone"] is None:
            raise HTTPException(status_code=422, detail="Owner phone number is required")
        changes["phone"] = changes["phone"].strip()
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).strip().lower()
    if changes.get("is_active") is None and "is_active" in changes:
        raise HTTPException(status_code=422, detail="Account activity must be true or false")
    before_data = {
        field: getattr(owner, field)
        for field in changes
    }

    for field, value in changes.items():
        setattr(owner, field, value)

    changed_fields = [
        field
        for field in changes
        if before_data.get(field) != getattr(owner, field)
    ]
    if not changed_fields:
        return company_owner_account_response(membership)

    revoke_user_sessions(db, owner.id)
    after_data = {
        field: getattr(owner, field)
        for field in changed_fields
    }
    record_platform_owner_account_change(
        db,
        admin=admin,
        owner=owner,
        company_id=company.id,
        action="platform.company_owner_login_updated",
        description="The platform owner updated company-owner login details.",
        changed_fields=changed_fields,
        before_data={field: before_data.get(field) for field in changed_fields},
        after_data=after_data,
    )
    db.add(
        Notification(
            user_id=owner.id,
            actor_user_id=admin.id,
            title="Account access details updated",
            message="The LoanHub system owner updated your account access details. Contact support if you did not expect this change.",
            notification_type=NotificationType.SYSTEM,
            entity_type="company_owner_account",
            entity_id=str(owner.id),
            action_url="/profile",
            icon="user-round-cog",
            priority="high",
            data={"company_id": str(company.id), "company_name": company.name},
        )
    )

    try:
        db.commit()
        db.refresh(owner)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone number or email address is already in use") from error
    return company_owner_account_response(membership)


@router.post(
    "/{company_id}/owner-account/temporary-password",
    response_model=CompanyOwnerTemporaryPasswordRead,
)
def create_company_owner_temporary_password(
    company_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_owner),
):
    company = company_or_404(db, company_id)
    membership = company_owner_membership_or_404(db, company_id)
    owner = membership.user
    previous_password_change_required = owner.must_change_password
    temporary_password = generate_temporary_password()

    owner.password_hash = hash_password(temporary_password)
    owner.must_change_password = True
    revoke_user_sessions(db, owner.id)
    record_platform_owner_account_change(
        db,
        admin=admin,
        owner=owner,
        company_id=company.id,
        action="platform.company_owner_temporary_password_created",
        description="The platform owner created a one-time company-owner password and revoked existing sessions.",
        changed_fields=["password_hash", "must_change_password"],
        before_data={"must_change_password": previous_password_change_required},
        after_data={"must_change_password": True},
    )
    db.add(
        Notification(
            user_id=owner.id,
            actor_user_id=admin.id,
            title="Temporary password issued",
            message="A temporary password was issued for your account. You must replace it immediately after signing in.",
            notification_type=NotificationType.SYSTEM,
            entity_type="company_owner_account",
            entity_id=str(owner.id),
            action_url="/change-password",
            icon="key-round",
            priority="high",
            data={"company_id": str(company.id), "company_name": company.name},
        )
    )
    db.commit()

    return CompanyOwnerTemporaryPasswordRead(
        user_id=owner.id,
        temporary_password=temporary_password,
        message="Share this password securely. It is displayed only once and must be changed after login.",
    )


@router.put("/{company_id}", response_model=LoanCompanyRead)
def update_company(
    company_id: UUID,
    payload: LoanCompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = company_or_404(db, company_id)
    assert_can_manage_company(db, current_user, company_id)

    changes = payload.model_dump(exclude_unset=True)
    if current_user.role != UserRole.SUPERADMIN:
        changes.pop("status", None)
        changes.pop("is_active", None)

    for field, value in changes.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}/branding", response_model=CompanyBrandingRead)
def get_company_branding(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = company_or_404(db, company_id)
    if current_user.role != UserRole.SUPERADMIN and not membership_for(db, current_user.id, company_id):
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    data = company_branding_payload(db, company)
    left = db.get(ManagedFile, data["left_logo_file_id"]) if data.get("left_logo_file_id") else None
    right = db.get(ManagedFile, data["right_logo_file_id"]) if data.get("right_logo_file_id") else None
    return CompanyBrandingRead(
        company_id=company.id,
        left_logo_file=left,
        right_logo_file=right,
        left_logo_download_url=data.get("left_logo_download_url"),
        right_logo_download_url=data.get("right_logo_download_url"),
    )


@router.get("/{company_id}/branding/logo/content")
def get_resolved_company_branding_logo(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company = company_or_404(db, company_id)
    if (
        current_user.role != UserRole.SUPERADMIN
        and not membership_for(db, current_user.id, company_id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Cross-company access is not allowed",
        )

    logo = resolve_company_document_logo(db, company.id)
    if not logo:
        raise HTTPException(status_code=404, detail="Company logo is not configured")

    return Response(
        content=logo.data,
        media_type=logo.media_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "X-LoanHub-Logo-Source": logo.source,
        },
    )


@router.post("/{company_id}/branding/logo-left", response_model=CompanyBrandingUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_company_left_logo(
    company_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company = company_or_404(db, company_id)
    assert_can_manage_company(db, context.user, company_id)
    existing = db.query(ManagedFile).filter(ManagedFile.company_id == company_id, ManagedFile.is_deleted.is_(False), ManagedFile.category == "company_logo_left").all()
    for item in existing:
        item.is_deleted = True
    await save_upload(
        db,
        file,
        context,
        category="company_logo_left",
        visibility="company",
        description="Company document header logo (left)",
        linked_entity_type="company_branding",
        linked_entity_id=str(company_id),
        is_confidential=False,
        company_id=company_id,
    )
    db.commit()
    return _branding_response(db, company, "Left logo uploaded successfully.")


@router.post("/{company_id}/branding/logo-right", response_model=CompanyBrandingUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_company_right_logo(
    company_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company = company_or_404(db, company_id)
    assert_can_manage_company(db, context.user, company_id)
    existing = db.query(ManagedFile).filter(ManagedFile.company_id == company_id, ManagedFile.is_deleted.is_(False), ManagedFile.category == "company_logo_right").all()
    for item in existing:
        item.is_deleted = True
    await save_upload(
        db,
        file,
        context,
        category="company_logo_right",
        visibility="company",
        description="Company document header logo (right)",
        linked_entity_type="company_branding",
        linked_entity_id=str(company_id),
        is_confidential=False,
        company_id=company_id,
    )
    db.commit()
    return _branding_response(db, company, "Right logo uploaded successfully.")


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    company = company_or_404(
        db,
        company_id,
    )

    dependencies = get_company_dependency_counts(
        db,
        company_id,
    )

    protected_dependencies = {
        key: value
        for key, value in dependencies.items()
        if key
        in {
            "loan_offers",
            "loans",
            "payments",
            "subscriptions",
            "marketplace_unlocks",
            "marketplace_access_requests",
        }
        and value > 0
    }

    if protected_dependencies:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "This company has financial or marketplace "
                    "history and cannot be permanently deleted. "
                    "Deactivate or suspend the company instead."
                ),
                "company_id": str(company_id),
                "dependencies": protected_dependencies,
            },
        )

    try:
        # Remove nonfinancial tenant configuration through mapped ORM
        # instances so every deletion is captured by the audit stream.
        employee_profiles = (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.company_id == company_id)
            .all()
        )
        for employee_profile in employee_profiles:
            db.delete(employee_profile)

        staff_members = (
            db.query(CompanyStaff)
            .filter(CompanyStaff.company_id == company_id)
            .all()
        )
        for staff_member in staff_members:
            db.delete(staff_member)

        loan_products = (
            db.query(LoanProduct)
            .filter(LoanProduct.company_id == company_id)
            .all()
        )
        for loan_product in loan_products:
            db.delete(loan_product)

        branches = (
            db.query(CompanyBranch)
            .filter(CompanyBranch.company_id == company_id)
            .all()
        )
        for branch in branches:
            db.delete(branch)

        db.delete(company)
        db.commit()

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "The company cannot be deleted because "
                    "related records still exist."
                ),
                "company_id": str(company_id),
                "dependencies": dependencies,
            },
        ) from error

def set_company_status(db: Session, company_id: UUID, new_status: CompanyStatus, active: bool) -> LoanCompany:
    company = company_or_404(db, company_id)
    company.status = new_status
    company.is_active = active
    db.commit()
    db.refresh(company)
    return company


@router.patch("/{company_id}/approve", response_model=LoanCompanyRead)
def approve_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return set_company_status(db, company_id, CompanyStatus.APPROVED, True)


@router.patch("/{company_id}/reject", response_model=LoanCompanyRead)
def reject_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return set_company_status(db, company_id, CompanyStatus.REJECTED, False)


@router.patch("/{company_id}/activate", response_model=LoanCompanyRead)
def activate_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    company = company_or_404(db, company_id)
    if company.status != CompanyStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Only approved companies can be activated")
    company.is_active = True
    db.commit()
    db.refresh(company)
    return company


@router.patch("/{company_id}/deactivate", response_model=LoanCompanyRead)
def deactivate_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    company = company_or_404(db, company_id)
    company.is_active = False
    db.commit()
    db.refresh(company)
    return company


@router.patch("/{company_id}/suspend", response_model=LoanCompanyRead)
def suspend_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return set_company_status(db, company_id, CompanyStatus.SUSPENDED, False)
