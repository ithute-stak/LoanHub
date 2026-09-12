from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.access_control import PERFORMANCE_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.schemas.performance import PerformanceOverviewRead
from database.session import get_db
from services.performance_service import build_performance_overview


router = APIRouter(prefix="/performance", tags=["Performance Analytics"])


@router.get("/overview", response_model=PerformanceOverviewRead)
def performance_overview(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    return build_performance_overview(
        db,
        company_id=None if context.is_platform_admin else context.company_id,
        branch_id=None if context.is_platform_admin else context.branch_id,
    )
