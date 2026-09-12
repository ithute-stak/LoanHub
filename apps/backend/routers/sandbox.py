from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, get_current_active_user
from database.config.config import settings
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.user import User
from database.session import get_db


router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


class SandboxRoleSwitchRequest(BaseModel):
    role: UserRole


def _require_sandbox_runtime() -> None:
    if not settings.SANDBOX_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _require_sandbox_tester(user: User) -> None:
    _require_sandbox_runtime()
    if not settings.SANDBOX_ROLE_SWITCH_ENABLED or user.phone != settings.SANDBOX_LOGIN_PHONE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sandbox role switching is not available for this account",
        )


@router.get("/status")
def sandbox_status():
    _require_sandbox_runtime()
    return {
        "sandbox": True,
        "isolated": True,
        "writable": True,
        "sample_clients": 5,
        "login_phone": settings.SANDBOX_LOGIN_PHONE,
        "available_roles": [role.value for role in UserRole],
        "message": "This environment contains synthetic demo data and is isolated from production.",
    }


@router.post("/switch-role")
def switch_sandbox_role(
    payload: SandboxRoleSwitchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_sandbox_tester(current_user)

    if payload.role in COMPANY_ROLES:
        membership = (
            db.query(CompanyStaff.id)
            .filter(
                CompanyStaff.user_id == current_user.id,
                CompanyStaff.role == payload.role,
                CompanyStaff.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The sandbox tester is missing the requested company-role membership",
            )

    current_user.role = payload.role
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {
        "role": current_user.role.value,
        "message": "Sandbox role changed. Refresh the current user session to apply navigation changes.",
    }
