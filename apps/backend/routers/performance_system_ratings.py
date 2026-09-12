from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import PERFORMANCE_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.session import get_db
from services.performance_service import build_performance_overview


router = APIRouter(prefix="/performance", tags=["Performance Analytics"])


class SystemPerformanceComponent(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    evidence: str


class SystemEmployeeRating(BaseModel):
    staff_id: UUID
    employee_id: UUID | None = None
    employee_name: str
    role: str
    job_title: str | None = None
    department: str | None = None
    score: float = Field(ge=0, le=100)
    rating: str
    confidence_percent: float = Field(ge=0, le=100)
    evidence_level: str
    components: list[SystemPerformanceComponent]


class SystemEmployeeRatingsRead(BaseModel):
    methodology: str
    employees: list[SystemEmployeeRating]


def _rating(score: float) -> str:
    if score >= 90:
        return "Exceptional"
    if score >= 80:
        return "Exceeds expectations"
    if score >= 70:
        return "Strong"
    if score >= 60:
        return "Meets expectations"
    if score >= 50:
        return "Developing"
    return "Needs attention"


def _evidence_level(confidence: float) -> str:
    if confidence >= 75:
        return "high"
    if confidence >= 50:
        return "moderate"
    if confidence >= 25:
        return "limited"
    return "insufficient"


def _employee_rating(employee) -> SystemEmployeeRating:
    components: list[SystemPerformanceComponent] = []

    if employee.offers_created > 0:
        conversion = min(100.0, employee.offers_accepted / employee.offers_created * 100)
        components.append(SystemPerformanceComponent(
            key="offer_conversion",
            label="Offer conversion",
            score=round(conversion, 2),
            weight=0.20,
            evidence=f"{employee.offers_accepted} accepted of {employee.offers_created} offers created",
        ))

    operational_events = employee.offers_created + employee.loans_approved + employee.loans_disbursed
    if operational_events > 0:
        activity_score = min(
            100.0,
            employee.offers_created * 4 + employee.loans_approved * 8 + employee.loans_disbursed * 10,
        )
        components.append(SystemPerformanceComponent(
            key="operational_activity",
            label="Operational delivery",
            score=round(activity_score, 2),
            weight=0.25,
            evidence=(
                f"{employee.offers_created} offers, {employee.loans_approved} approvals, "
                f"{employee.loans_disbursed} disbursements"
            ),
        ))

    if employee.payment_transactions > 0:
        payment_score = min(100.0, employee.payment_transactions * 8)
        components.append(SystemPerformanceComponent(
            key="payments",
            label="Payment processing",
            score=round(payment_score, 2),
            weight=0.20,
            evidence=f"{employee.payment_transactions} payment transactions processed",
        ))

    goal_count = employee.active_goals + employee.completed_goals
    if goal_count > 0:
        components.append(SystemPerformanceComponent(
            key="goals",
            label="Goal attainment",
            score=max(0.0, min(100.0, employee.goal_completion_percent)),
            weight=0.20,
            evidence=f"{goal_count} tracked goals; {employee.completed_goals} completed",
        ))

    if employee.average_review_score > 0:
        components.append(SystemPerformanceComponent(
            key="reviews",
            label="Recorded performance reviews",
            score=max(0.0, min(100.0, employee.average_review_score)),
            weight=0.15,
            evidence=f"Recorded review average {employee.average_review_score:.1f}/100",
        ))

    available_weight = sum(component.weight for component in components)
    if available_weight <= 0:
        score = 0.0
        confidence = 0.0
        rating = "Insufficient data"
    else:
        score = round(
            sum(component.score * component.weight for component in components) / available_weight,
            2,
        )
        confidence = round(min(100.0, available_weight * 100), 2)
        rating = _rating(score)

    return SystemEmployeeRating(
        staff_id=employee.staff_id,
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        role=employee.role,
        job_title=employee.job_title,
        department=employee.department,
        score=score,
        rating=rating,
        confidence_percent=confidence,
        evidence_level=_evidence_level(confidence),
        components=components,
    )


@router.get("/system-ratings", response_model=SystemEmployeeRatingsRead)
def system_employee_ratings(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    overview = build_performance_overview(
        db,
        company_id=None if context.is_platform_admin else context.company_id,
        branch_id=None if context.is_platform_admin else context.branch_id,
    )
    rows = [_employee_rating(employee) for employee in overview.employees]
    rows.sort(key=lambda item: (item.confidence_percent, item.score), reverse=True)
    return SystemEmployeeRatingsRead(
        methodology=(
            "LoanHub computes ratings only from metrics for which the employee has evidence. "
            "Missing role-irrelevant activity is not treated as poor performance. Confidence shows how much "
            "of the available metric model is supported by recorded system evidence; managers should review "
            "low-confidence ratings before using them for employment decisions."
        ),
        employees=rows,
    )
