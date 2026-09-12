from __future__ import annotations

import hashlib
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import get_current_active_user
from core.security import get_current_local_user, verify_password
from database.models.user import User
from database.session import get_db
from services.account_security_service import record_account_event
from services.ithute_auth_service import (
    IthuteAuthDisabled,
    IthuteAuthUnavailable,
    decode_ithute_access_token,
    get_ithute_auth_settings,
)


router = APIRouter(prefix="/auth/ithute", tags=["Authentication"])


class IthuteLinkRequest(BaseModel):
    access_token: str = Field(min_length=100, max_length=8192)


class IthuteUnlinkRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)


def _verified_central_subject(access_token: str) -> UUID:
    try:
        claims = decode_ithute_access_token(access_token)
        return UUID(str(claims["sub"]))
    except IthuteAuthDisabled as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="!thute Auth is not enabled for LoanHub yet",
        ) from error
    except IthuteAuthUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="!thute Auth verification is temporarily unavailable",
        ) from error
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The !thute Auth token is invalid or expired",
        ) from error


def _subject_hash(subject: UUID) -> str:
    return hashlib.sha256(str(subject).encode("utf-8")).hexdigest()


@router.get("/status")
def central_auth_status(
    current_user: User = Depends(get_current_active_user),
):
    config = get_ithute_auth_settings()
    return {
        "enabled": config.enabled,
        "issuer": config.resolved_issuer,
        "audience": config.audience,
        "linked": current_user.auth_user_id is not None,
        "auth_user_id": str(current_user.auth_user_id) if current_user.auth_user_id else None,
        "auth_source": getattr(current_user, "_auth_source", "loanhub"),
    }


@router.post("/link")
def link_central_account(
    payload: IthuteLinkRequest,
    request: Request,
    current_user: User = Depends(get_current_local_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    central_subject = _verified_central_subject(payload.access_token)
    linked_elsewhere = db.query(User.id).filter(
        User.auth_user_id == central_subject,
        User.id != current_user.id,
    ).first()
    if linked_elsewhere:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This !thute account is already linked to another LoanHub account",
        )

    if current_user.auth_user_id and current_user.auth_user_id != central_subject:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This LoanHub account is already linked to a different !thute account",
        )

    current_user.auth_user_id = central_subject
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.ithute_linked",
        description="The LoanHub account was linked to a central !thute identity.",
        severity="high",
        event_data={"central_subject_hash": _subject_hash(central_subject)},
    )
    db.commit()
    return {
        "linked": True,
        "auth_user_id": str(central_subject),
        "message": "!thute account linked. Central LoanHub access tokens are now accepted.",
    }


@router.post("/unlink")
def unlink_central_account(
    payload: IthuteUnlinkRequest,
    request: Request,
    current_user: User = Depends(get_current_local_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    if not verify_password(payload.current_password, str(current_user.password_hash)):
        raise HTTPException(status_code=400, detail="The LoanHub account password is incorrect")

    previous_subject = current_user.auth_user_id
    if previous_subject is None:
        return {"linked": False, "message": "No !thute account is linked."}

    current_user.auth_user_id = None
    record_account_event(
        db,
        user=current_user,
        request=request,
        action="auth.ithute_unlinked",
        description="The central !thute identity link was removed from the LoanHub account.",
        severity="critical",
        event_data={"central_subject_hash": _subject_hash(previous_subject)},
    )
    db.commit()
    return {
        "linked": False,
        "message": "!thute account unlinked. Existing LoanHub authentication remains available.",
    }
