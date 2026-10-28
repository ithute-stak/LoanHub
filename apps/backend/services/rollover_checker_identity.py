"""Fail-closed identity and tenancy validation for proposed reversal checker.

This verifies that the named checker is a real, active, verified company
finance/owner principal. It is NOT evidence that they approved this particular
reversal; a durable approval workflow is still required before activation.
"""
from fastapi import HTTPException
from database.models.user import User
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole

CHECKER_ROLES = frozenset({
    UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN,
    UserRole.FINANCE_OFFICER, UserRole.COMPLIANCE_OFFICER,
})


def verify_rollover_checker_identity(db, *, company_id, maker_user_id, checker_user_id):
    if checker_user_id == maker_user_id:
        raise HTTPException(status_code=409, detail="Maker cannot be the checker")
    checker = db.query(User).filter(
        User.id == checker_user_id,
        User.is_active.is_(True),
        User.is_verified.is_(True),
    ).one_or_none()
    if checker is None:
        raise HTTPException(status_code=409, detail="Checker must have an active verified account")
    company_role = db.query(CompanyStaff.id).filter(
        CompanyStaff.user_id == checker_user_id,
        CompanyStaff.company_id == company_id,
        CompanyStaff.is_active.is_(True),
        CompanyStaff.role.in_(CHECKER_ROLES),
    ).first()
    if company_role is None:
        raise HTTPException(status_code=409, detail="Checker lacks active finance approval authority in this company")
    return checker.id
