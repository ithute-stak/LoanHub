from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.models.employer_group import EmployerGroup
from database.schemas.employer_group import EmployerGroupCreate
from utils.work_group_policy import (
    WORK_GROUP_CODES,
    WORK_GROUP_POLICY,
    work_group_policy_for,
)


_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 /._&-]{0,39}$")


def _unsupported_work_group() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "Unsupported work group. Select one of LoanHub's central work groups: "
            + ", ".join(WORK_GROUP_CODES)
            + "."
        ),
    )


def ensure_central_work_groups(db: Session) -> tuple[int, int]:
    """Persist LoanHub's canonical work-group catalogue idempotently.

    Missing canonical records are created. Existing canonical records are
    repaired back to the centrally defined name and active state. The function
    deliberately ignores non-central employer-group rows so legacy data is not
    deleted or rewritten unexpectedly.

    Returns ``(created_count, updated_count)``.
    """
    existing_groups = (
        db.query(EmployerGroup)
        .filter(EmployerGroup.code.in_(WORK_GROUP_CODES))
        .all()
    )
    groups_by_code = {group.code: group for group in existing_groups}

    created_count = 0
    updated_count = 0

    for policy in WORK_GROUP_POLICY:
        group = groups_by_code.get(policy.code)
        if group is None:
            group = EmployerGroup(
                code=policy.code,
                name=policy.name,
                is_active=True,
            )
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Work-group code must contain letters, numbers or the supported "
                "separators / . _ & - and be at most 40 characters."
            ),
        )

    policy = work_group_policy_for(code)
    if policy is None:
        raise _unsupported_work_group()
    return policy.code


def normalize_employer_group_name(value: str) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if len(name) < 2 or len(name) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Work-group name must be between 2 and 200 characters.",
        )
    return name


def _central_group_or_422(group: EmployerGroup | None) -> EmployerGroup:
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected work group is not available.",
        )

    policy = work_group_policy_for(group.code)
    if policy is None:
        raise _unsupported_work_group()
    return group


def resolve_employer_group(
    db: Session,
    *,
    employer_group_id: UUID | None = None,
    new_employer_group: EmployerGroupCreate | None = None,
) -> EmployerGroup | None:
    """Resolve a borrower work group from LoanHub's central catalogue.

    ``new_employer_group`` remains accepted at the API boundary for backwards
    compatibility with older clients, but it can only resolve to one of the
    centrally supported groups. Registration can no longer create arbitrary
    employer/group rows.
    """
    if employer_group_id and new_employer_group is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select one central work group, not both.",
        )

    if employer_group_id:
        group = (
            db.query(EmployerGroup)
            .filter(
                EmployerGroup.id == employer_group_id,
                EmployerGroup.is_active.is_(True),
            )
            .first()
        )
        return _central_group_or_422(group)

    if new_employer_group is None:
        return None

    policy = (
        work_group_policy_for(new_employer_group.code)
        or work_group_policy_for(new_employer_group.name)
    )
    if policy is None:
        raise _unsupported_work_group()

    group = (
        db.query(EmployerGroup)
        .filter(
            EmployerGroup.code == policy.code,
            EmployerGroup.is_active.is_(True),
        )
        .first()
    )
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Central work group {policy.code} is not available. "
                "Contact a LoanHub administrator."
            ),
        )
    return group
