from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.ai_intelligence import AIIntelligenceGuardrailEvent, AIIntelligenceInsight, AIIntelligenceRun
from database.models.collection_automation import CollectionWorkItem
from database.models.credit_committee import CreditCommitteeCase, CreditCommitteeCondition
from database.models.portfolio_risk import PortfolioRiskSnapshot
from database.models.professional_lending import DirectLoanApplication


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
ALLOWED_FEEDBACK = {"useful", "not_useful", "incorrect", "actioned", "dismissed"}


def _fingerprint(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _add_insight(
    db: Session,
    run: AIIntelligenceRun,
    *,
    insight_type: str,
    domain: str,
    severity: str,
    confidence: Decimal,
    entity_type: str,
    entity_id: UUID | None,
    folio_number: str | None,
    title: str,
    explanation: str,
    recommended_action: str,
    rationale: list[str],
    evidence: dict[str, Any],
    branch_id: UUID | None = None,
) -> AIIntelligenceInsight:
    row = AIIntelligenceInsight(
        run_id=run.id,
        company_id=run.company_id,
        branch_id=branch_id,
        insight_type=insight_type,
        domain=domain,
        severity=severity,
        confidence_percent=confidence,
        entity_type=entity_type,
        entity_id=entity_id,
        folio_number=folio_number,
        title=title,
        explanation=explanation,
        recommended_action=recommended_action,
        rationale=rationale,
        evidence=evidence,
        fingerprint=_fingerprint(insight_type, entity_type, entity_id, folio_number, title),
    )
    db.add(row)
    return row


def generate_intelligence_run(db: Session, context: TenantContext, *, run_type: str = "on_demand") -> AIIntelligenceRun:
    now = datetime.now(timezone.utc)
    run = AIIntelligenceRun(
        company_id=context.company_id,
        branch_id=context.branch_id,
        run_reference=f"AI-{now:%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}",
        run_type=run_type,
        status="running",
        model_version="explainable-v1",
        evidence_cutoff_at=now,
        triggered_by_user_id=context.user.id,
        started_at=now,
    )
    db.add(run)
    db.flush()

    snapshot_query = db.query(PortfolioRiskSnapshot).filter(PortfolioRiskSnapshot.company_id == context.company_id)
    if context.branch_id:
        snapshot_query = snapshot_query.filter(PortfolioRiskSnapshot.branch_id == context.branch_id)
    latest_date = snapshot_query.with_entities(PortfolioRiskSnapshot.snapshot_date).order_by(PortfolioRiskSnapshot.snapshot_date.desc()).first()
    snapshots = []
    if latest_date:
        snapshots = snapshot_query.filter(PortfolioRiskSnapshot.snapshot_date == latest_date[0]).all()

    for row in snapshots:
        if row.outstanding_balance <= 0:
            continue
        severity = None
        reasons: list[str] = []
        confidence = Decimal("78.00")
        if row.days_past_due >= 90:
            severity = "critical"
            reasons.append(f"Loan is {row.days_past_due} days past due")
        elif row.days_past_due >= 30:
            severity = "high"
            reasons.append(f"Loan is {row.days_past_due} days past due")
        elif row.days_past_due >= 8:
            severity = "medium"
            reasons.append(f"Loan is {row.days_past_due} days past due")
        if row.first_payment_default:
            severity = "critical" if severity == "high" else (severity or "high")
            reasons.append("First-payment default signal is present")
            confidence = min(Decimal("95.00"), confidence + Decimal("8.00"))
        if row.is_top_up and row.days_past_due >= 8:
            reasons.append("This exposure is a top-up loan")
        if severity:
            _add_insight(
                db, run,
                insight_type="loan_deterioration",
                domain="portfolio_risk",
                severity=severity,
                confidence=confidence,
                entity_type="loan",
                entity_id=row.loan_id,
                folio_number=(row.evidence_snapshot or {}).get("folio_number"),
                title=f"Escalating repayment risk · {(row.evidence_snapshot or {}).get('folio_number') or 'loan'}",
                explanation="The latest portfolio evidence shows repayment stress that merits human review. This is an advisory signal, not a default prediction or automated lending decision.",
                recommended_action="Review the loan history and current collection case, then assign or reprioritise the appropriate recovery action.",
                rationale=reasons,
                evidence={"snapshot_date": row.snapshot_date.isoformat(), "days_past_due": row.days_past_due, "bucket": row.delinquency_bucket, "outstanding_balance": str(row.outstanding_balance), "overdue_amount": str(row.overdue_amount)},
                branch_id=row.branch_id,
            )

    work_query = db.query(CollectionWorkItem).filter(
        CollectionWorkItem.company_id == context.company_id,
        CollectionWorkItem.status.in_(["open", "in_progress"]),
    )
    if context.branch_id:
        work_query = work_query.filter(CollectionWorkItem.branch_id == context.branch_id)
    for item in work_query.order_by(CollectionWorkItem.priority_score.desc()).limit(300).all():
        if item.priority not in {"high", "critical", "urgent"} and Decimal(str(item.priority_score or 0)) < Decimal("70"):
            continue
        _add_insight(
            db, run,
            insight_type="collection_priority",
            domain="collections",
            severity="high" if item.priority != "critical" else "critical",
            confidence=Decimal("88.00"),
            entity_type="collection_work_item",
            entity_id=item.id,
            folio_number=(item.context_snapshot or {}).get("folio_number"),
            title=f"High-priority recovery task · {item.treatment_code}",
            explanation="The recovery engine has already classified this case as high priority. The intelligence layer is surfacing it because urgency and outstanding treatment evidence align.",
            recommended_action=f"Complete or reassign the {item.action_type.replace('_', ' ')} treatment before its due time and record evidence of the outcome.",
            rationale=[f"Priority score {item.priority_score}", f"Recovery path {item.recovery_path}", f"Treatment {item.treatment_code}"],
            evidence={"due_at": item.due_at.isoformat(), "priority": item.priority, "priority_score": str(item.priority_score), "attempt_count": item.attempt_count, "reason": item.reason},
            branch_id=item.branch_id,
        )

    app_query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.company_id == context.company_id,
        DirectLoanApplication.status.in_(["submitted", "under_review"]),
    )
    if context.branch_id:
        app_query = app_query.filter(DirectLoanApplication.branch_id == context.branch_id)
    for app in app_query.limit(300).all():
        case = db.query(CreditCommitteeCase).filter(
            CreditCommitteeCase.company_id == context.company_id,
            CreditCommitteeCase.application_id == app.id,
        ).first()
        reasons: list[str] = []
        severity = "low"
        if app.credit_warning:
            reasons.append("Application contains credit-warning evidence")
            severity = "medium"
        if app.credit_committee_required and not case:
            reasons.append("Credit Committee case has not yet been opened")
            severity = "high"
        elif case and case.status not in {"approved", "conditionally_approved", "rejected", "closed"}:
            reasons.append(f"Committee case remains {case.status}")
            severity = max(severity, "medium", key=lambda value: SEVERITY_ORDER[value])
        if reasons:
            _add_insight(
                db, run,
                insight_type="underwriting_attention",
                domain="underwriting",
                severity=severity,
                confidence=Decimal("84.00"),
                entity_type="application",
                entity_id=app.id,
                folio_number=None,
                title=f"Underwriting attention · {app.application_reference}",
                explanation="The application has unresolved governance or evidence signals. Human underwriting and committee controls remain authoritative.",
                recommended_action="Open the application and complete the outstanding underwriting/committee step before any approval or disbursement action.",
                rationale=reasons,
                evidence={"application_status": app.status, "requested_amount": str(app.requested_amount), "committee_required": bool(app.credit_committee_required), "committee_case_status": case.status if case else None},
                branch_id=app.branch_id,
            )

    condition_query = db.query(CreditCommitteeCondition).join(CreditCommitteeCase, CreditCommitteeCase.id == CreditCommitteeCondition.case_id).filter(
        CreditCommitteeCase.company_id == context.company_id,
        CreditCommitteeCondition.status.notin_(["satisfied", "waived"]),
        CreditCommitteeCondition.condition_type.in_(["pre_contract", "pre_disbursement"]),
    )
    if context.branch_id:
        condition_query = condition_query.filter(CreditCommitteeCase.branch_id == context.branch_id)
    for condition in condition_query.limit(200).all():
        case = db.get(CreditCommitteeCase, condition.case_id)
        _add_insight(
            db, run,
            insight_type="approval_condition",
            domain="underwriting",
            severity="high" if condition.condition_type == "pre_disbursement" else "medium",
            confidence=Decimal("96.00"),
            entity_type="credit_condition",
            entity_id=condition.id,
            folio_number=None,
            title=f"Unresolved {condition.condition_type.replace('_', ' ')} condition",
            explanation="A formal Credit Committee condition remains unresolved. LoanHub governance prevents bypassing this control.",
            recommended_action="Satisfy the condition with evidence or formally waive it under authorised controls before continuing the governed stage.",
            rationale=[condition.title],
            evidence={"case_reference": case.case_reference if case else None, "condition_status": condition.status, "due_date": condition.due_date.isoformat() if condition.due_date else None},
            branch_id=case.branch_id if case else context.branch_id,
        )

    db.flush()
    insights = db.query(AIIntelligenceInsight).filter(AIIntelligenceInsight.run_id == run.id).all()
    counts = defaultdict(int)
    for row in insights:
        counts[row.severity] += 1
    run.insight_count = len(insights)
    run.critical_count = counts["critical"]
    run.high_count = counts["high"]
    run.medium_count = counts["medium"]
    run.low_count = counts["low"]
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        "advisory_only": True,
        "human_decision_required": True,
        "generated_from": ["portfolio_risk", "collections", "credit_committee", "direct_applications"],
    }
    db.add(AIIntelligenceGuardrailEvent(
        company_id=context.company_id,
        event_type="run_completed_advisory_only",
        actor_user_id=context.user.id,
        detail={"run_id": str(run.id), "insight_count": len(insights), "model_version": run.model_version},
        occurred_at=run.completed_at,
    ))
    db.commit()
    db.refresh(run)
    return run


def run_payload(run: AIIntelligenceRun) -> dict[str, Any]:
    return {
        "id": str(run.id), "run_reference": run.run_reference, "run_type": run.run_type,
        "status": run.status, "model_version": run.model_version,
        "evidence_cutoff_at": run.evidence_cutoff_at.isoformat(), "insight_count": run.insight_count,
        "critical_count": run.critical_count, "high_count": run.high_count,
        "medium_count": run.medium_count, "low_count": run.low_count,
        "summary": run.summary or {}, "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def insight_payload(row: AIIntelligenceInsight) -> dict[str, Any]:
    return {
        "id": str(row.id), "run_id": str(row.run_id), "insight_type": row.insight_type,
        "domain": row.domain, "severity": row.severity,
        "confidence_percent": float(row.confidence_percent or 0), "entity_type": row.entity_type,
        "entity_id": str(row.entity_id) if row.entity_id else None, "folio_number": row.folio_number,
        "title": row.title, "explanation": row.explanation, "recommended_action": row.recommended_action,
        "rationale": row.rationale or [], "evidence": row.evidence or {}, "status": row.status,
        "feedback": row.feedback, "feedback_note": row.feedback_note,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def review_insight(db: Session, context: TenantContext, insight_id: UUID, *, status: str, feedback: str | None, note: str | None) -> AIIntelligenceInsight:
    row = db.query(AIIntelligenceInsight).filter(
        AIIntelligenceInsight.id == insight_id,
        AIIntelligenceInsight.company_id == context.company_id,
    ).first()
    if not row or (context.branch_id and row.branch_id not in {None, context.branch_id}):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="AI intelligence insight was not found")
    if status not in {"reviewed", "dismissed", "actioned"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Status must be reviewed, dismissed or actioned")
    if feedback and feedback not in ALLOWED_FEEDBACK:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Unsupported feedback value")
    row.status = status
    row.feedback = feedback
    row.feedback_note = (note or "").strip() or None
    row.reviewed_by_user_id = context.user.id
    row.reviewed_at = datetime.now(timezone.utc)
    db.add(AIIntelligenceGuardrailEvent(
        company_id=context.company_id,
        insight_id=row.id,
        event_type="human_feedback_recorded",
        actor_user_id=context.user.id,
        detail={"status": status, "feedback": feedback, "note": row.feedback_note},
        occurred_at=row.reviewed_at,
    ))
    db.commit()
    db.refresh(row)
    return row
