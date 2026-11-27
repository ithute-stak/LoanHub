"""Read-only Batlokoa attendance directory; disabled unless explicitly configured."""
import os
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session

from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, UserRole
from database.models.user import User
from database.session import get_db

router = APIRouter(prefix="/integrations/attendance", tags=["Attendance Integration"])
ROLES = {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN, UserRole.BRANCH_MANAGER,
         UserRole.LOAN_OFFICER, UserRole.CREDIT_ANALYST}


def authorize_directory(company_id: UUID, authorization: str | None) -> None:
    configured = os.getenv("BATLOKOA_ATTENDANCE_DIRECTORY_TOKEN", "")
    scope = os.getenv("BATLOKOA_ATTENDANCE_DIRECTORY_COMPANY_ID", "")
    if (os.getenv("BATLOKOA_ATTENDANCE_DIRECTORY_ENABLED") != "true"
            or not 32 <= len(configured) <= 4096
            or any(not 33 <= ord(c) <= 126 for c in configured)):
        raise HTTPException(503, "Attendance directory disabled")
    try:
        allowed = UUID(scope)
    except ValueError:
        raise HTTPException(503, "Attendance directory disabled") from None
    if (not authorization or not authorization.isascii()
            or len(authorization) > 4103
            or not secrets.compare_digest(authorization, "Bearer " + configured)):
        raise HTTPException(401, "Service authentication required")
    if company_id != allowed:
        raise HTTPException(403, "Company scope denied")


@router.get("/employees", include_in_schema=False)
def employees(response: Response, company_id: UUID,
              limit: int = Query(100, ge=1, le=100),
              authorization: str | None = Header(None),
              db: Session = Depends(get_db)):
    authorize_directory(company_id, authorization)
    response.headers["Cache-Control"] = "no-store"
    company = db.query(LoanCompany.id).filter(
        LoanCompany.id == company_id, LoanCompany.is_active.is_(True),
        LoanCompany.status == CompanyStatus.APPROVED).first()
    if company is None:
        raise HTTPException(403, "Company unavailable")
    # Multiple membership roles are permitted in LoanHub. Only a unique
    # active eligible primary membership is accepted; ambiguous users are
    # excluded from reminders, not assigned an arbitrary role.
    rows = db.query(CompanyStaff.user_id, CompanyStaff.role,
                    CompanyStaff.is_active, CompanyStaff.is_primary, User.is_active).join(
        User, User.id == CompanyStaff.user_id).filter(
        CompanyStaff.company_id == company_id).order_by(
        CompanyStaff.user_id, CompanyStaff.id).limit(1001).all()
    if len(rows) > 1000:
        raise HTTPException(503, "Directory exceeds supported bounds")
    grouped = {}
    for uid, role, active, primary, user_active in rows:
        grouped.setdefault(uid, []).append((role, active, primary, user_active))
    result = []
    for uid, memberships in grouped.items():
        eligible = [role for role, active, primary, user_active in memberships
                    if active is True and primary is True and user_active is True and role in ROLES]
        if len(eligible) != 1:
            continue
        result.append({"company_id": str(company_id), "employee_id": str(uid),
                       "role": eligible[0].value, "active": True})
    if len(result) > limit:
        raise HTTPException(503, "Directory exceeds supported bounds")
    return {"company_id": str(company_id), "complete": True, "employees": result}
