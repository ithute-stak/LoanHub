from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from core.access_control import get_current_active_user
from core.security import hash_password, verify_password
from database.models.audit_log import AuditLog
from database.models.company_client_identity_change import CompanyClientIdentityChangeRequest
from database.models.company_staff import CompanyStaff
from database.models.person import Person
from database.models.user import RefreshToken, User
from database.schemas.account import (
    AccountActivityRead,
    AccountContactUpdate,
    AccountMembershipRead,
    AccountOverviewRead,
    AccountPersonUpdate,
    AccountSecurityRead,
    AccountSessionActionResponse,
    AccountSessionRead,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from database.schemas.auth import AuthMembershipRead, AuthUserRead
from database.schemas.company_clients import (
    CompanyClientNationalIdChangeDecision,
    CompanyClientNationalIdChangeRequestRead,
)
from database.schemas.person_schema import PersonRead
from database.session import get_db
from services.account_security_service import record_account_event
from services.borrower_identity_change_service import (
    approve_as_borrower,
    reject_identity_change_request,
    serialize_identity_change_request,
)
from utils.decode_encode_token import ALGORITHM, PUBLIC_KEY


router = APIRouter(prefix="/auth/account", tags=["My account"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _serialize_user(user: User) -> AuthUserRead:
    memberships = [
        AuthMembershipRead.model_validate(item)
        for item in user.company_staff
        if item.is_active
    ]
    return AuthUserRead(
        id=user.id,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        person=user.person,
        memberships=memberships,
    )


def _load_account_user(db: Session, user_id: UUID) -> User:
    user = (
        db.query(User)
        .options(
            selectinload(User.person),
            selectinload(User.company_staff).selectinload(CompanyStaff.company),
            selectinload(User.company_staff).selectinload(CompanyStaff.branch),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    return user




def _access_token_payload(request: Request) -> dict:
    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return {}
    try:
        return jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return {}


def _is_impersonated(request: Request) -> bool:
    return bool(_access_token_payload(request).get("impersonated_by"))


def _require_direct_account_access(request: Request) -> None:
    if _is_impersonated(request):
        raise HTTPException(
            status_code=403,
            detail="Account and security changes are disabled during an impersonation session",
        )

def _current_refresh_jti(request: Request) -> str | None:
    token = request.cookies.get("refresh_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("token_type") != "refresh":
        return None
    return payload.get("jti")


def _assert_unique_identity(
    db: Session,
    *,
    national_id: str | None,
    passport_number: str | None,
    exclude_person_id: UUID | None,
) -> None:
    filters = []
    if national_id:
        filters.append(Person.national_id == national_id)
    if passport_number:
        filters.append(Person.passport_number == passport_number)
    if not filters:
        return
    query = db.query(Person.id).filter(or_(*filters))
    if exclude_person_id:
        query = query.filter(Person.id != exclude_person_id)
    if query.first():
        raise HTTPException(status_code=409, detail="National ID or passport number already exists")


def _validate_new_password(user: User, payload: ChangePasswordRequest) -> None:
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=422, detail="New password confirmation does not match")
    if verify_password(payload.new_password, str(user.password_hash)):
        raise HTTPException(status_code=422, detail="Choose a password different from the current password")
    password = payload.new_password
    checks = (
        any(character.islower() for character in password),
        any(character.isupper() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    )
    if not all(checks):
        raise HTTPException(
            status_code=422,
            detail="Password must contain uppercase, lowercase, number and special characters",
        )
    lowered = password.lower()
    if user.phone and user.phone.lower() in lowered:
        raise HTTPException(status_code=422, detail="Password must not contain your phone number")
    if user.email and user.email.split("@", 1)[0].lower() in lowered:
        raise HTTPException(status_code=422, detail="Password must not contain your email name")


@router.get("", response_model=AccountOverviewRead)
def get_account_overview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = _load_account_user(db, current_user.id)
    active_sessions = (
        db.query(RefreshToken.id)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > _now(),
        )
        .count()
    )
    memberships = [
        AccountMembershipRead(
            id=item.id,
            company_id=item.company_id,
            company_name=item.company.name if item.company else "Company",
            branch_id=item.branch_id,
            branch_name=item.branch.name if item.branch else None,
            role=item.role,
            is_primary=item.is_primary,
            is_active=item.is_active,
        )
        for item in user.company_staff
    ]
    return AccountOverviewRead(
        user=_serialize_user(user),
        memberships=memberships,
        security=AccountSecurityRead(
            active_sessions=active_sessions,
            last_seen_at=user.last_seen_at,
            account_created_at=user.created_at,
            account_updated_at=user.updated_at,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_impersonated=_is_impersonated(request),
            can_manage_security=not _is_impersonated(request),
        ),
    )


@router.patch("/contact", response_model=AuthUserRead)
def update_account_contact(
    payload: AccountContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    user = _load_account_user(db, current_user.id)
    if not verify_password(payload.current_password, str(user.password_hash)):
        record_account_event(
            db,
            user=user,
            request=request,
            action="account.contact_update_failed",
            description="Contact update was rejected because the current password was invalid.",
            status="failed",
            severity="warning",
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    changes = payload.model_dump(exclude_unset=True, exclude={"current_password"})
    changed_fields: list[str] = []
    if "email" in changes:
        email = str(changes["email"]).strip().lower() if changes["email"] else None
        if email != user.email:
            if email and db.query(User.id).filter(User.email == email, User.id != user.id).first():
                raise HTTPException(status_code=409, detail="Email address is already in use")
            user.email = email
            changed_fields.append("email")
    if "phone" in changes:
        phone = str(changes["phone"] or "").strip()
        if not phone:
            raise HTTPException(status_code=422, detail="Phone number is required")
        if phone != user.phone:
            if db.query(User.id).filter(User.phone == phone, User.id != user.id).first():
                raise HTTPException(status_code=409, detail="Phone number is already in use")
            user.phone = phone
            changed_fields.append("phone")

    if not changed_fields:
        raise HTTPException(status_code=400, detail="No contact changes were supplied")

    user.is_verified = False
    record_account_event(
        db,
        user=user,
        request=request,
        action="account.contact_updated",
        description="The authenticated user updated account contact details.",
        changed_fields=changed_fields,
        event_data={"verification_reset": True},
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone or email already exists") from error
    return _serialize_user(_load_account_user(db, user.id))


@router.put("/profile", response_model=PersonRead)
def update_account_profile(
    payload: AccountPersonUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    user = _load_account_user(db, current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    for field in (
        "middle_name",
        "national_id",
        "passport_number",
        "nationality",
        "district",
        "town_or_village",
        "physical_address",
    ):
        if field in changes:
            changes[field] = _clean_optional(changes[field])

    person = user.person
    if not person:
        if not changes.get("first_name") or not changes.get("last_name"):
            raise HTTPException(
                status_code=422,
                detail="First name and last name are required to create the personal profile",
            )
        _assert_unique_identity(
            db,
            national_id=changes.get("national_id"),
            passport_number=changes.get("passport_number"),
            exclude_person_id=None,
        )
        person = Person(user_id=user.id, **changes)
        db.add(person)
    else:
        if "national_id" in changes:
            requested_national_id = _clean_optional(changes.get("national_id"))
            current_national_id = _clean_optional(person.national_id)
            if requested_national_id != current_national_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "National ID changes require approval from the borrower and a company owner. "
                        "Ask the lending company to create an identity-change request."
                    ),
                )
            changes.pop("national_id", None)
        _assert_unique_identity(
            db,
            national_id=person.national_id,
            passport_number=changes.get("passport_number", person.passport_number),
            exclude_person_id=person.id,
        )
        for field, value in changes.items():
            setattr(person, field, value)

    record_account_event(
        db,
        user=user,
        request=request,
        action="account.profile_updated",
        description="The authenticated user updated personal profile information.",
        changed_fields=changes.keys(),
    )
    try:
        db.commit()
        db.refresh(person)
        return person
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Identity information is already in use") from error


@router.get(
    "/national-id-change-requests",
    response_model=list[CompanyClientNationalIdChangeRequestRead],
)
def list_my_national_id_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = _load_account_user(db, current_user.id)
    if user.person is None:
        return []
    rows = (
        db.query(CompanyClientIdentityChangeRequest)
        .filter(CompanyClientIdentityChangeRequest.person_id == user.person.id)
        .order_by(CompanyClientIdentityChangeRequest.created_at.desc())
        .limit(30)
        .all()
    )
    return [serialize_identity_change_request(row) for row in rows]


@router.post(
    "/national-id-change-requests/{request_id}/decision",
    response_model=CompanyClientNationalIdChangeRequestRead,
)
def decide_my_national_id_change_request(
    request_id: UUID,
    payload: CompanyClientNationalIdChangeDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = _load_account_user(db, current_user.id)
    if user.person is None:
        raise HTTPException(status_code=404, detail="Personal identity profile not found")
    row = (
        db.query(CompanyClientIdentityChangeRequest)
        .filter(
            CompanyClientIdentityChangeRequest.id == request_id,
            CompanyClientIdentityChangeRequest.person_id == user.person.id,
        )
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="National ID change request not found")
    if payload.approve:
        approve_as_borrower(db, row=row, borrower_user_id=user.id)
    else:
        reject_identity_change_request(
            db,
            row=row,
            user_id=user.id,
            actor_role="borrower",
            reason=payload.reason,
        )
    db.commit()
    db.refresh(row)
    return serialize_identity_change_request(row)


@router.post("/password", response_model=ChangePasswordResponse)
def change_account_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    user = _load_account_user(db, current_user.id)
    if not verify_password(payload.current_password, str(user.password_hash)):
        record_account_event(
            db,
            user=user,
            request=request,
            action="account.password_change_failed",
            description="Password change was rejected because the current password was invalid.",
            status="failed",
            severity="warning",
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    _validate_new_password(user, payload)
    user.password_hash = hash_password(payload.new_password)
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked.is_(False),
    ).all()
    for token in tokens:
        token.revoked = True
    record_account_event(
        db,
        user=user,
        request=request,
        action="account.password_changed",
        description="Password changed successfully and every refresh session was revoked.",
        severity="high",
        changed_fields=["password_hash"],
        event_data={"revoked_sessions": len(tokens)},
    )
    db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return ChangePasswordResponse(
        message="Password changed. Sign in again with the new password.",
        requires_reauthentication=True,
    )


@router.get("/sessions", response_model=list[AccountSessionRead])
def list_account_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    current_jti = _current_refresh_jti(request)
    rows = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == current_user.id)
        .order_by(RefreshToken.created_at.desc())
        .limit(50)
        .all()
    )
    now = _now()
    results: list[AccountSessionRead] = []
    for row in rows:
        expires_at = _normalise_datetime(row.expires_at)
        active = not row.revoked and expires_at > now
        if row.revoked:
            session_status = "revoked"
        elif expires_at <= now:
            session_status = "expired"
        else:
            session_status = "active"
        results.append(
            AccountSessionRead(
                id=row.id,
                created_at=row.created_at,
                expires_at=row.expires_at,
                is_current=row.jti == current_jti,
                is_active=active,
                status=session_status,
            )
        )
    return results


@router.delete("/sessions/{session_id}", response_model=AccountSessionActionResponse)
def revoke_account_session(
    session_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    session = (
        db.query(RefreshToken)
        .filter(RefreshToken.id == session_id, RefreshToken.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.jti == _current_refresh_jti(request):
        raise HTTPException(status_code=400, detail="Use logout to close the current session")
    changed = 0
    if not session.revoked:
        session.revoked = True
        changed = 1
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="account.session_revoked",
        description="The authenticated user revoked a signed-in session.",
        severity="warning",
        event_data={"session_id": str(session.id)},
    )
    db.commit()
    return AccountSessionActionResponse(message="Session revoked.", revoked_count=changed)


@router.post("/sessions/revoke-others", response_model=AccountSessionActionResponse)
def revoke_other_account_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    current_jti = _current_refresh_jti(request)
    query = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked.is_(False),
    )
    if current_jti:
        query = query.filter(RefreshToken.jti != current_jti)
    sessions = query.all()
    for session in sessions:
        session.revoked = True
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="account.other_sessions_revoked",
        description="The authenticated user signed out all other sessions.",
        severity="warning",
        event_data={"revoked_sessions": len(sessions)},
    )
    db.commit()
    return AccountSessionActionResponse(
        message="Other sessions signed out.",
        revoked_count=len(sessions),
    )


@router.post("/sessions/revoke-all", response_model=AccountSessionActionResponse)
def revoke_all_account_sessions(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    sessions = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked.is_(False),
    ).all()
    for session in sessions:
        session.revoked = True
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="account.all_sessions_revoked",
        description="The authenticated user signed out every account session.",
        severity="high",
        event_data={"revoked_sessions": len(sessions)},
    )
    db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return AccountSessionActionResponse(
        message="All sessions signed out.",
        revoked_count=len(sessions),
    )


@router.get("/activity", response_model=list[AccountActivityRead])
def list_account_activity(
    request: Request,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_direct_account_access(request)
    safe_limit = max(1, min(limit, 100))
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == current_user.id,
            or_(
                AuditLog.entity_type == "account_security",
                AuditLog.action.like("auth.%"),
                AuditLog.action.like("account.%"),
            ),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    return [
        AccountActivityRead(
            id=row.id,
            action=row.action,
            description=row.description,
            status=row.status,
            severity=row.severity,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            changed_fields=list(row.changed_fields or []),
            event_data=dict(row.event_data or {}),
            created_at=row.created_at,
        )
        for row in rows
    ]
