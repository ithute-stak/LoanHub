from __future__ import annotations

import os
from datetime import datetime, timezone

from core.security import hash_password, verify_password
from database.models.enums import UserRole
from database.models.governance_control import UserMFAEnrollment, UserSecurityState
from database.models.user import RefreshToken, User
from database.session import SessionLocal


DEFAULT_SYSTEM_OWNER_PHONE = "59001394"


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    phone = os.getenv("SYSTEM_OWNER_PHONE", DEFAULT_SYSTEM_OWNER_PHONE).strip()
    password = os.getenv("SYSTEM_OWNER_PASSWORD", "")
    email = os.getenv("SYSTEM_OWNER_EMAIL", "").strip().lower() or None
    reset_mfa = _flag("SYSTEM_OWNER_RESET_MFA", False)

    if not phone:
        raise SystemExit("SYSTEM_OWNER_PHONE cannot be empty")
    if len(password) < 12:
        raise SystemExit("SYSTEM_OWNER_PASSWORD must contain at least 12 characters")

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.phone == phone)
            .with_for_update()
            .first()
        )

        created = False
        if user is None:
            user = User(
                phone=phone,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
                must_change_password=False,
            )
            db.add(user)
            db.flush()
            created = True
        else:
            if email and not user.email:
                user.email = email
            user.password_hash = hash_password(password)
            user.role = UserRole.SUPERADMIN
            user.is_active = True
            user.is_verified = True
            user.must_change_password = False
            db.add(user)
            db.flush()

        state = (
            db.query(UserSecurityState)
            .filter(UserSecurityState.user_id == user.id)
            .with_for_update()
            .first()
        )
        if state is None:
            state = UserSecurityState(user_id=user.id)
            db.add(state)
            db.flush()

        state.failed_login_attempts = 0
        state.locked_until = None
        state.last_failed_login_at = None
        state.session_version = int(state.session_version or 1) + 1
        db.add(state)

        (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
            .update({"revoked": True}, synchronize_session=False)
        )

        if reset_mfa:
            enrollment = (
                db.query(UserMFAEnrollment)
                .filter(UserMFAEnrollment.user_id == user.id)
                .with_for_update()
                .first()
            )
            if enrollment is not None:
                enrollment.is_enabled = False
                enrollment.disabled_at = datetime.now(timezone.utc).replace(tzinfo=None)
                enrollment.recovery_code_hashes = []
                enrollment.last_accepted_counter = None
                db.add(enrollment)

        db.commit()
        db.refresh(user)

        if not verify_password(password, str(user.password_hash)):
            raise SystemExit("System owner password verification failed after update")
        if user.role != UserRole.SUPERADMIN or not user.is_active or not user.is_verified:
            raise SystemExit("System owner account verification failed after update")

        action = "created" if created else "synchronized"
        print(
            f"LoanHub system owner {action}: phone={user.phone}, "
            f"role={user.role.value}, active={user.is_active}, verified={user.is_verified}, "
            f"mfa_reset={reset_mfa}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
