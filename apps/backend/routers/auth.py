from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.responses import JSONResponse

from core.access_control import get_current_active_user, require_platform_admin
from core.security import DUMMY_PASSWORD_HASH, authenticate_user, hash_password, verify_password
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
    MFAConfirmRequest,
    MFADisableRequest,
    MFAEnrollmentResponse,
    PasswordChangeRequest,
    PasswordResetRequestCreate,
    PasswordResetRequestResponse,
    SessionRead,
    WebSocketSessionRequest,
    WebSocketSessionResponse,
)
from database.schemas.user import UserRead, UserUpdate
from database.session import get_db
from services.account_security_service import record_account_event
from services.mfa_service import (
    begin_enrollment,
    ensure_not_locked,
    enrollment_secret,
    otpauth_uri,
    register_login_failure,
    register_login_success,
    revoke_all_sessions,
    security_state,
    verify_second_factor,
    verify_totp,
)
from database.models.governance_control import UserMFAEnrollment
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
        must_change_password=user.must_change_password,
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
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = load_user_by_phone(db, payload.phone.strip())
    if user:
        ensure_not_locked(db, user)
    password_valid = verify_password(
        payload.password,
        str(user.password_hash) if user else DUMMY_PASSWORD_HASH,
    )
    if not user or not password_valid:
        if user:
            state = register_login_failure(db, user)
            record_account_event(
                db,
                user=user,
                request=request,
                action="auth.login_failed",
                description="A sign-in attempt failed because the supplied password was invalid.",
                status="failed",
                severity="high" if state.locked_until else "warning",
                event_data={"account_locked": bool(state.locked_until)},
            )
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    if not user.is_active:
        record_account_event(
            db,
            user=user,
            request=request,
            action="auth.login_blocked",
            description="A sign-in attempt was blocked because the account is inactive.",
            status="failed",
            severity="high",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Account is inactive")

    if not verify_second_factor(
        db,
        user,
        otp=payload.otp,
        recovery_code=payload.recovery_code,
    ):
        state = register_login_failure(db, user)
        record_account_event(
            db,
            user=user,
            request=request,
            action="auth.mfa_failed",
            description="A sign-in attempt failed additional account verification.",
            status="failed",
            severity="high" if state.locked_until else "warning",
            event_data={"account_locked": bool(state.locked_until)},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Additional verification is required")

    state = register_login_success(db, user)
    refresh_token, jti, expires_at = create_refresh_token(
        {
            "user_id": str(user.id),
            "token_type": "refresh",
            "session_version": int(state.session_version or 1),
        }
    )
    access_token = authenticate_user(user, session_version=int(state.session_version or 1), session_jti=jti)
    ip_value = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
    db.add(RefreshToken(
        jti=jti,
        user_id=user.id,
        expires_at=expires_at,
        session_version=str(state.session_version or 1),
        device_name=(payload.device_name or "").strip()[:160] or None,
        ip_hash=hashlib.sha256(ip_value.encode()).hexdigest(),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    ))
    record_account_event(
        db,
        user=user,
        request=request,
        action="auth.login_succeeded",
        description="The user signed in successfully.",
        event_data={"session_expires_at": expires_at.isoformat()},
    )
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


@router.post("/mfa/enroll", response_model=MFAEnrollmentResponse)
def enroll_mfa(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _enrollment, secret, recovery_codes = begin_enrollment(db, current_user)
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.mfa_enrollment_started",
        description="Multi-factor authentication enrollment was started.",
        severity="warning",
    )
    db.commit()
    return MFAEnrollmentResponse(
        otpauth_uri=otpauth_uri(current_user, secret),
        recovery_codes=recovery_codes,
        message="Scan the authenticator URI, store the recovery codes securely, then confirm one code.",
    )


@router.get("/mfa/status")
def mfa_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    enrollment = db.query(UserMFAEnrollment).filter(UserMFAEnrollment.user_id == current_user.id).first()
    return {
        "enabled": bool(enrollment and enrollment.is_enabled),
        "enrollment_pending": bool(enrollment and not enrollment.is_enabled and not enrollment.disabled_at),
        "recovery_codes_remaining": len(enrollment.recovery_code_hashes or []) if enrollment and enrollment.is_enabled else 0,
        "confirmed_at": enrollment.confirmed_at if enrollment else None,
    }


@router.post("/mfa/confirm")
def confirm_mfa(
    payload: MFAConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    enrollment = db.query(UserMFAEnrollment).filter(
        UserMFAEnrollment.user_id == current_user.id,
        UserMFAEnrollment.is_enabled.is_(False),
    ).with_for_update().first()
    if not enrollment:
        raise HTTPException(status_code=409, detail="No pending MFA enrollment was found")
    counter = verify_totp(enrollment_secret(enrollment), payload.otp)
    if counter is None:
        raise HTTPException(status_code=400, detail="The authenticator code is invalid or expired")
    enrollment.last_accepted_counter = counter
    enrollment.is_enabled = True
    enrollment.confirmed_at = datetime.now(timezone.utc)
    revoked = revoke_all_sessions(db, current_user)
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.mfa_enabled",
        description="Multi-factor authentication was enabled and existing sessions were revoked.",
        severity="high",
        event_data={"sessions_revoked": revoked},
    )
    db.commit()
    return {"message": "MFA enabled. Sign in again with your authenticator code."}


@router.post("/mfa/disable")
def disable_mfa(
    payload: MFADisableRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.password, str(current_user.password_hash)):
        raise HTTPException(status_code=400, detail="The account password is incorrect")
    enrollment = db.query(UserMFAEnrollment).filter(
        UserMFAEnrollment.user_id == current_user.id,
        UserMFAEnrollment.is_enabled.is_(True),
    ).first()
    if not enrollment:
        raise HTTPException(status_code=409, detail="MFA is not enabled")
    if not verify_second_factor(db, current_user, otp=payload.otp, recovery_code=payload.recovery_code):
        raise HTTPException(status_code=400, detail="Additional verification failed")
    enrollment.is_enabled = False
    enrollment.disabled_at = datetime.now(timezone.utc)
    enrollment.recovery_code_hashes = []
    revoked = revoke_all_sessions(db, current_user)
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.mfa_disabled",
        description="Multi-factor authentication was disabled and existing sessions were revoked.",
        severity="critical",
        event_data={"sessions_revoked": revoked},
    )
    db.commit()
    return {"message": "MFA disabled. Sign in again."}


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    current_jti = None
    cookie = request.cookies.get("refresh_token")
    if cookie:
        try:
            current_jti = decode_token(cookie).get("jti")
        except Exception:
            current_jti = None
    sessions = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ).order_by(RefreshToken.created_at.desc()).all()
    return [SessionRead(
        jti=item.jti,
        device_name=item.device_name,
        user_agent=item.user_agent,
        created_at=item.created_at,
        last_used_at=item.last_used_at,
        expires_at=item.expires_at,
        current=item.jti == current_jti,
    ) for item in sessions]


@router.delete("/sessions/{session_jti}")
def revoke_session(
    session_jti: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    token = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.jti == session_jti,
        RefreshToken.revoked.is_(False),
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Active session not found")
    token.revoked = True
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.session_revoked",
        description="A selected account session was revoked.",
        severity="warning",
        event_data={"session_jti_hash": hashlib.sha256(session_jti.encode()).hexdigest()},
    )
    db.commit()
    return {"message": "Session revoked"}


@router.post("/sessions/revoke-all")
def revoke_every_session(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = revoke_all_sessions(db, current_user)
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.sessions_revoked_all",
        description="All account sessions were revoked.",
        severity="high",
        event_data={"sessions_revoked": count},
    )
    db.commit()
    return {"message": "All sessions revoked", "sessions_revoked": count}


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

    client_id = (
        payload.client_id.strip()
        if payload.client_id
        else None
    )
    is_production = settings.ENVIRONMENT.lower() == "production"

    token = create_token(
        {
            "user_id": str(current_user.id),
            "token_type": "websocket",
            "company_id": (
                str(selected_company_id)
                if selected_company_id
                else None
            ),
            "client_id": client_id,
            "jti": uuid.uuid4().hex,
        },
        timedelta(seconds=WS_SESSION_TTL_SECONDS),
    )

    response = JSONResponse(
        WebSocketSessionResponse(
            websocket_token=token,
            expires_in=WS_SESSION_TTL_SECONDS,
        ).model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
        },
    )
    response.set_cookie(
        key=WS_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
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
                        icon="key-round",
                        priority="high",
                        data={
                            "request_reference": request_reference,
                            "request_ip": request.client.host if request.client else None,
                            "action_label": "Contact user securely",
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


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, str(current_user.password_hash)):
        raise HTTPException(status_code=400, detail="The current password is incorrect")

    new_password = payload.new_password
    if not (
        any(character.islower() for character in new_password)
        and any(character.isupper() for character in new_password)
        and any(character.isdigit() for character in new_password)
    ):
        raise HTTPException(
            status_code=422,
            detail="The new password must include uppercase, lowercase and numeric characters",
        )
    if verify_password(new_password, str(current_user.password_hash)):
        raise HTTPException(status_code=400, detail="Choose a password different from the current password")

    current_user.password_hash = hash_password(new_password)
    current_user.must_change_password = False
    revoke_all_sessions(db, current_user)
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.password_changed",
        description="The account password was changed and all existing sessions were revoked.",
        severity="warning",
        changed_fields=("password_hash", "must_change_password"),
        event_data={"sessions_revoked": True},
    )
    db.commit()
    return {"message": "Password changed successfully. Sign in again with the new password."}


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
    state = security_state(db, user)
    if int(payload.get("session_version", 1)) != int(state.session_version or 1):
        raise HTTPException(status_code=401, detail="Session has been revoked")

    db_token.revoked = True
    db_token.last_used_at = datetime.now(timezone.utc)
    new_refresh, new_jti, new_exp = create_refresh_token(
        {
            "user_id": str(user.id),
            "token_type": "refresh",
            "session_version": int(state.session_version or 1),
        }
    )
    access_token = authenticate_user(user, session_version=int(state.session_version or 1), session_jti=new_jti)
    db.add(RefreshToken(
        jti=new_jti,
        user_id=user.id,
        expires_at=new_exp,
        session_version=str(state.session_version or 1),
        device_name=db_token.device_name,
        ip_hash=db_token.ip_hash,
        user_agent=db_token.user_agent,
    ))
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
                user = load_user(db, db_token.user_id)
                if user:
                    record_account_event(
                        db,
                        user=user,
                        request=request,
                        action="auth.logout",
                        description="The user signed out of the current session.",
                    )
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
    target_security_state = security_state(db, target)
    access_token = create_token(
        {
            'user_id': str(target.id),
            'role': target.role.value,
            'token_type': 'access',
            'session_version': int(target_security_state.session_version or 1),
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
