from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.responses import JSONResponse

from core.access_control import get_current_active_user, require_platform_admin
from core.security import authenticate_user, hash_password, verify_password
from database.config.config import settings
from database.models.audit_log import AuditLog
from database.models.company_staff import CompanyStaff
from database.models.notification import Notification
from database.models.enums import NotificationType, UserRole
from database.models.user import RefreshToken, User
from database.schemas.auth import (
    AuthMembershipRead,
    AuthUserRead,
    ImpersonationRequest,
    ImpersonationResponse,
    ImpersonationTargetRead,
    LoginRequest,
    LoginResponse,
    PasswordResetRequestCreate,
    PasswordResetRequestResponse,
    WebSocketSessionRequest,
    WebSocketSessionResponse,
)
from database.schemas.user import UserRead, UserUpdate
from database.session import get_db
from utils.decode_encode_token import (
    ALGORITHM,
    PUBLIC_KEY,
    create_refresh_token,
    create_token,
    decode_token,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


def serialize_user(user: User) -> AuthUserRead:
    memberships = [
        AuthMembershipRead.model_validate(membership)
        for membership in user.company_staff
        if membership.is_active
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


def load_user(db: Session, user_id) -> User | None:
    return (
        db.query(User)
        .options(
            selectinload(User.person),
            selectinload(User.company_staff),
        )
        .filter(User.id == user_id)
        .first()
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = load_user_by_phone(db, payload.phone.strip())
    if not user or not verify_password(payload.password, str(user.password_hash)):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    access_token = authenticate_user(user)
    refresh_token, jti, expires_at = create_refresh_token(
        {"user_id": str(user.id), "token_type": "refresh"}
    )
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    db.commit()

    body = LoginResponse(
        access_token=access_token,
        user=serialize_user(user),
    ).model_dump(mode="json")
    response = JSONResponse(body)
    set_refresh_cookie(response, refresh_token)
    return response


def load_user_by_phone(db: Session, phone: str) -> User | None:
    return (
        db.query(User)
        .options(selectinload(User.person), selectinload(User.company_staff))
        .filter(User.phone == phone)
        .first()
    )


def set_refresh_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_EXPIRE_DAYS,
        path="/api/v1/auth",
    )


WS_SESSION_COOKIE = "loanhub_ws_session"
WS_SESSION_TTL_SECONDS = 90


@router.post(
    "/websocket-session",
    response_model=WebSocketSessionResponse,
)
def create_websocket_session(
    payload: WebSocketSessionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Prepare a short-lived HttpOnly WebSocket authentication cookie.

    The browser WebSocket API cannot set an Authorization header. Using a
    short-lived cookie avoids exposing the main access token in URLs or
    relying on proxies to preserve a JWT-bearing subprotocol.
    """
    selected_company_id = payload.company_id

    if selected_company_id and current_user.role != UserRole.SUPERADMIN:
        membership_exists = (
            db.query(CompanyStaff.id)
            .filter(
                CompanyStaff.user_id == current_user.id,
                CompanyStaff.company_id == selected_company_id,
                CompanyStaff.is_active.is_(True),
            )
            .first()
            is not None
        )
        if not membership_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company access denied",
            )

    token = create_token(
        {
            "user_id": str(current_user.id),
            "token_type": "websocket",
            "company_id": (
                str(selected_company_id)
                if selected_company_id
                else None
            ),
        },
        timedelta(seconds=WS_SESSION_TTL_SECONDS),
    )

    response = JSONResponse(
        WebSocketSessionResponse(
            expires_in=WS_SESSION_TTL_SECONDS,
        ).model_dump(mode="json")
    )
    response.set_cookie(
        key=WS_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() == "production",
        samesite="lax",
        max_age=WS_SESSION_TTL_SECONDS,
        path="/api/v1/ws",
    )
    return response


@router.post(
    "/password-reset-request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    payload: PasswordResetRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a privacy-safe support request without revealing account existence."""
    identifier = payload.identifier.strip().lower()
    request_reference = f"RST-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    user = (
        db.query(User)
        .filter(
            or_(
                User.phone == payload.identifier.strip(),
                User.email == identifier,
            )
        )
        .first()
    )

    if user:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        already_notified = (
            db.query(Notification.id)
            .filter(
                Notification.entity_type == "password_reset_requests",
                Notification.entity_id == str(user.id),
                Notification.created_at >= recent_cutoff,
            )
            .first()
            is not None
        )

        if not already_notified:
            admins = (
                db.query(User.id)
                .filter(
                    User.role == UserRole.SUPERADMIN,
                    User.is_active.is_(True),
                )
                .all()
            )
            display_name = (
                user.person.full_name
                if user.person and user.person.full_name
                else user.email or user.phone
            )
            for (admin_id,) in admins:
                db.add(
                    Notification(
                        user_id=admin_id,
                        actor_user_id=user.id,
                        title="Password-reset support request",
                        message=(
                            f"{display_name} requested help restoring account access. "
                            f"Reference: {request_reference}."
                        ),
                        notification_type=NotificationType.SYSTEM,
                        entity_type="password_reset_requests",
                        entity_id=str(user.id),
                        action_url="/superadmin/chat",
                        action_label="Contact user securely",
                        icon="key-round",
                        priority="high",
                        data={
                            "request_reference": request_reference,
                            "request_ip": request.client.host if request.client else None,
                        },
                    )
                )
            db.commit()

    return PasswordResetRequestResponse(
        message=(
            "If the account exists, the platform support team has received a secure "
            "access-recovery request. No password or PIN is required."
        ),
        request_reference=request_reference,
    )


@router.get("/me", response_model=AuthUserRead)
def me(current_user: User = Depends(get_current_active_user)):
    return serialize_user(current_user)


@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from error

    if payload.get("token_type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")

    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.jti == payload.get("jti"),
            RefreshToken.revoked.is_(False),
        )
        .first()
    )
    if not db_token:
        raise HTTPException(status_code=401, detail="Refresh token is revoked")

    user = load_user(db, payload.get("user_id"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")

    db_token.revoked = True
    access_token = authenticate_user(user)
    new_refresh, new_jti, new_exp = create_refresh_token(
        {"user_id": str(user.id), "token_type": "refresh"}
    )
    db.add(RefreshToken(jti=new_jti, user_id=user.id, expires_at=new_exp))
    db.commit()

    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    set_refresh_cookie(response, new_refresh)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = decode_token(token)
            db_token = db.query(RefreshToken).filter(RefreshToken.jti == payload.get("jti")).first()
            if db_token:
                db_token.revoked = True
                db.commit()
        except Exception:
            # Logout must remain idempotent even for an expired or malformed cookie.
            db.rollback()

    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return response


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = payload.model_dump(exclude_unset=True)
    if "password_hash" in changes and changes["password_hash"]:
        changes["password_hash"] = hash_password(changes["password_hash"])

    for field, value in changes.items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone or email already exists") from error


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_platform_admin),
):
    if str(current_admin.id) == str(user_id):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()



@router.get('/impersonation-targets', response_model=list[ImpersonationTargetRead])
def impersonation_targets(
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    if not settings.ENABLE_ROLE_IMPERSONATION:
        raise HTTPException(status_code=403, detail='Role switching is disabled')

    query = (
        db.query(User)
        .options(
            selectinload(User.person),
            selectinload(User.company_staff),
        )
        .filter(User.is_active.is_(True), User.role != UserRole.SUPERADMIN)
    )
    users = query.order_by(User.created_at.desc()).limit(500).all()
    token = (search or '').strip().lower()
    results: list[ImpersonationTargetRead] = []
    for user in users:
        name = (
            user.person.full_name
            if user.person and user.person.full_name
            else user.email or user.phone
        )
        memberships = [item for item in user.company_staff if item.is_active]
        rows = memberships or [None]
        for membership in rows:
            company = membership.company if membership else None
            branch = membership.branch if membership else None
            role = membership.role if membership else user.role
            haystack = ' '.join(
                filter(None, [
                    name,
                    user.email,
                    user.phone,
                    role.value,
                    company.name if company else None,
                    branch.name if branch else None,
                ])
            ).lower()
            if token and token not in haystack:
                continue
            results.append(ImpersonationTargetRead(
                id=user.id,
                display_name=name,
                email=user.email,
                phone=user.phone,
                role=role,
                company_id=membership.company_id if membership else None,
                company_name=company.name if company else None,
                branch_id=membership.branch_id if membership else None,
                branch_name=branch.name if branch else None,
            ))
    return results


@router.post('/impersonate', response_model=ImpersonationResponse)
def impersonate_user(
    payload: ImpersonationRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    if not settings.ENABLE_ROLE_IMPERSONATION:
        raise HTTPException(status_code=403, detail='Role switching is disabled')

    target = load_user(db, payload.target_user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=404, detail='Target account is unavailable')
    if target.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=400, detail='Switching into another platform-owner account is not allowed')

    selected_company_id = payload.company_id
    if selected_company_id:
        membership = db.query(CompanyStaff).filter(
            CompanyStaff.user_id == target.id,
            CompanyStaff.company_id == selected_company_id,
            CompanyStaff.is_active.is_(True),
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail='The target user does not belong to the selected company')

    duration = min(payload.duration_minutes, settings.IMPERSONATION_MAX_MINUTES)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration)
    access_token = create_token(
        {
            'user_id': str(target.id),
            'role': target.role.value,
            'token_type': 'access',
            'impersonated_by': str(admin.id),
            'impersonation_reason': payload.reason.strip(),
            'impersonation_company_id': str(selected_company_id) if selected_company_id else None,
        },
        timedelta(minutes=duration),
    )

    db.add(AuditLog(
        user_id=admin.id,
        company_id=selected_company_id,
        action='impersonated',
        table_name='users',
        entity_type='users',
        record_id=target.id,
        description='Platform owner started a time-limited support role-switch session.',
        actor_role=UserRole.SUPERADMIN.value,
        severity='warning',
        status='success',
        before_data={},
        after_data={'target_user_id': str(target.id), 'company_id': str(selected_company_id) if selected_company_id else None},
        changed_fields=[],
        event_data={'reason': payload.reason.strip(), 'expires_at': expires_at.isoformat()},
    ))
    db.commit()

    return ImpersonationResponse(
        access_token=access_token,
        expires_at=expires_at,
        user=serialize_user(target),
        original_admin=serialize_user(admin),
        company_id=selected_company_id,
        reason=payload.reason.strip(),
    )
