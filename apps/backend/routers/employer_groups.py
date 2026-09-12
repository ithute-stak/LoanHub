from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models.employer_group import EmployerGroup
from database.schemas.employer_group import EmployerGroupRead
from database.session import get_db
from utils.work_group_policy import WORK_GROUP_CODES, work_group_sort_key


router = APIRouter(prefix="/employer-groups", tags=["Employer Groups"])


@router.get("", response_model=list[EmployerGroupRead])
def list_employer_groups(
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=250, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(EmployerGroup).filter(
        EmployerGroup.is_active.is_(True),
        EmployerGroup.code.in_(WORK_GROUP_CODES),
    )
    term = str(search or "").strip()
    if term:
        value = f"%{term}%"
        query = query.filter(
            or_(
                EmployerGroup.code.ilike(value),
                EmployerGroup.name.ilike(value),
            )
        )

    groups = query.all()
    groups.sort(key=lambda group: work_group_sort_key(group.code))
    return groups[:limit]
