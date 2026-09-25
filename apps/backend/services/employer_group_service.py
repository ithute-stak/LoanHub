from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.models.employer_group import EmployerGroup
from database.schemas.employer_group import EmployerGroupCreate
from utils.work_group_policy import WORK_GROUP_CODES, WORK_GROUP_POLICY, work_group_policy_for


_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 /._&-]{0,39}$")


def ensure_central_work_groups(db: Session) -> tuple[int, int]:
    """Persist LoanHub's canonical work-group catalogue idempotently."""
    existing_groups = db.query(EmployerGroup).filter(EmployerGroup.code.in_(WORK_GROUP_CODES)).all()
    groups_by_code = {group.code: group for group in existing_groups}
    created_count = 0
    updated_count = 0
    for policy in WORK_GROUP_POLICY:
        group = groups_by_code.get(policy.code)
        if group is None:
            group = EmployerGroup(code=policy.code, name=policy.name, is_active=True)
            db.add(group)
            groups_by_code[policy.code] = group
            created_count += 1
            continue
        changed = False
        if group.name != policy.name:
            group.name = policy.name
            changed = True
        if not group.is_active:
            group.is_active = True
            changed = True
        if changed:
            updated_count += 1
    if created_count or updated_count:
        db.commit()
    return created_count, updated_count


def normalize_employer_group_code(value: str) -> str:
    code = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    if not code or not _CODE_PATTERN.fullmatch(code):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work-group code must contain letters, numbers or the supported separators / . _ & - and be at most 40 characters.")
    policy = work_group_policy_for(code)
    return policy.code if policy is not None else code


def normalize_employer_group_name(value: str) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if len(name) < 2 or len(name) > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work-group name must be between 2 and 200 characters.")
    return name


def resolve_employer_group(db: Session, *, employer_group_id: UUID | None = None, new_employer_group: EmployerGroupCreate | None = None) -> EmployerGroup | None:
    """Resolve an active work group, creating a new custom group when requested."""
    if employer_group_id and new_employer_group is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select one work group, not both.")
    if employer_group_id:
        group = db.query(EmployerGroup).filter(EmployerGroup.id == employer_group_id, EmployerGroup.is_active.is_(True)).first()
        if group is None:
            raise HTTPException(status_code=422, detail="The selected work group is not available.")
        return group
    if new_employer_group is None:
        return None
    name = normalize_employer_group_name(new_employer_group.name)
    central_policy = work_group_policy_for(new_employer_group.code) or work_group_policy_for(name)
    code = central_policy.code if central_policy is not None else normalize_employer_group_code(new_employer_group.code)
    existing = db.query(EmployerGroup).filter(EmployerGroup.code == code).first()
    if existing is not None:
        if central_policy is not None:
            existing.name = central_policy.name
        if not existing.is_active:
            existing.is_active = True
        db.flush()
        return existing
    if central_policy is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Central work group {central_policy.code} is not available. Contact a LoanHub administrator.")
    group = EmployerGroup(code=code, name=name, is_active=True)
    db.add(group)
    db.flush()
    return group
