from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.governance_control import UserMFAEnrollment, UserSecurityState
from database.models.user import User
from services.crypto_service import decrypt_control_secret, encrypt_control_secret


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _state(db: Session, user: User, *, lock: bool = False) -> UserSecurityState:
    query = db.query(UserSecurityState).filter(UserSecurityState.user_id == user.id)
    if lock:
        query = query.with_for_update()
    state = query.first()
    if state is None:
        state = UserSecurityState(user_id=user.id)
        db.add(state)
        db.flush()
    return state


def security_state(db: Session, user: User) -> UserSecurityState:
    return _state(db, user)


def ensure_not_locked(db: Session, user: User) -> UserSecurityState:
    state = _state(db, user, lock=True)
    now = _now()
    if state.locked_until and state.locked_until > now:
        remaining = max(1, int((state.locked_until - now).total_seconds()))
        raise HTTPException(
            status_code=423,
            detail="Account is temporarily locked. Try again later.",
            headers={"Retry-After": str(remaining)},
        )
    if state.locked_until and state.locked_until <= now:
        state.locked_until = None
        state.failed_login_attempts = 0
    return state


def register_login_failure(db: Session, user: User) -> UserSecurityState:
    state = _state(db, user, lock=True)
    now = _now()
    state.failed_login_attempts = int(state.failed_login_attempts or 0) + 1
    state.last_failed_login_at = now
    if state.failed_login_attempts >= settings.AUTH_LOCKOUT_MAX_ATTEMPTS:
        state.locked_until = now + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
        state.failed_login_attempts = 0
    db.add(state)
    return state


def register_login_success(db: Session, user: User) -> UserSecurityState:
    state = _state(db, user, lock=True)
    state.failed_login_attempts = 0
    state.locked_until = None
    state.last_successful_login_at = _now()
    db.add(state)
    return state


def revoke_all_sessions(db: Session, user: User) -> int:
    from database.models.user import RefreshToken

    state = _state(db, user, lock=True)
    state.session_version = int(state.session_version or 1) + 1
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .update({"revoked": True}, synchronize_session=False)
    )
    db.add(state)
    return int(count or 0)


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _secret_bytes(secret: str) -> bytes:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def totp_at(secret: str, counter: int, digits: int = 6) -> str:
    digest = hmac.new(_secret_bytes(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, *, timestamp: int | None = None, last_counter: int | None = None) -> int | None:
    if not code.isdigit() or len(code) != 6:
        return None
    current = int(timestamp if timestamp is not None else time.time()) // 30
    for counter in (current - 1, current, current + 1):
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(totp_at(secret, counter), code):
            return counter
    return None


def _hash_recovery_code(code: str) -> str:
    return hashlib.sha256(f"loanhub-mfa:{code.strip().upper()}".encode()).hexdigest()


def begin_enrollment(db: Session, user: User) -> tuple[UserMFAEnrollment, str, list[str]]:
    secret = generate_totp_secret()
    encrypted, nonce, version = encrypt_control_secret(secret, b"loanhub-mfa-totp-v1")
    recovery_codes = [secrets.token_hex(5).upper() for _ in range(10)]
    enrollment = db.query(UserMFAEnrollment).filter(UserMFAEnrollment.user_id == user.id).first()
    if enrollment is None:
        enrollment = UserMFAEnrollment(user_id=user.id, encrypted_secret=encrypted, encryption_nonce=nonce, encryption_version=version)
    enrollment.encrypted_secret = encrypted
    enrollment.encryption_nonce = nonce
    enrollment.encryption_version = version
    enrollment.recovery_code_hashes = [_hash_recovery_code(code) for code in recovery_codes]
    enrollment.is_enabled = False
    enrollment.confirmed_at = None
    enrollment.disabled_at = None
    enrollment.last_accepted_counter = None
    db.add(enrollment)
    return enrollment, secret, recovery_codes


def enrollment_secret(enrollment: UserMFAEnrollment) -> str:
    return decrypt_control_secret(
        enrollment.encrypted_secret,
        enrollment.encryption_nonce,
        enrollment.encryption_version,
        b"loanhub-mfa-totp-v1",
    )


def verify_second_factor(db: Session, user: User, *, otp: str | None, recovery_code: str | None) -> bool:
    enrollment = db.query(UserMFAEnrollment).filter(
        UserMFAEnrollment.user_id == user.id,
        UserMFAEnrollment.is_enabled.is_(True),
    ).with_for_update().first()
    if enrollment is None:
        return True
    if otp:
        counter = verify_totp(enrollment_secret(enrollment), otp.strip(), last_counter=enrollment.last_accepted_counter)
        if counter is not None:
            enrollment.last_accepted_counter = counter
            db.add(enrollment)
            return True
    if recovery_code:
        candidate = _hash_recovery_code(recovery_code)
        hashes = list(enrollment.recovery_code_hashes or [])
        for index, stored in enumerate(hashes):
            if hmac.compare_digest(stored, candidate):
                hashes.pop(index)
                enrollment.recovery_code_hashes = hashes
                db.add(enrollment)
                return True
    return False


def otpauth_uri(user: User, secret: str) -> str:
    label = (user.email or user.phone).replace(" ", "%20")
    issuer = settings.PRODUCT_NAME.replace(" ", "%20")
    return f"otpauth://totp/{issuer}:{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
