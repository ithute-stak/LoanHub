from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.client_loan_company import ClientCompanyLoan
from database.models.credit_committee import (
    CreditCommitteeCase,
    CreditCommitteeCondition,
    CreditCommitteeEvent,
    CreditCommitteeVote,
    UnderwritingAssessment,
)
from database.models.lending_operations import (
    CDASPayrollProfile,
    ComplianceCase,
    CreditBureauEnquiry,
    CreditDecision,
)
from database.models.origination import (
    AffordabilityAssessment,
    BorrowerDebtObligation,
    BorrowerEmploymentProfile,
    BorrowerKYCProfile,
)
from database.models.person import Person
from database.models.professional_lending import DirectLoanApplication
from database.models.user import User


MONEY = Decimal("0.01")
ASSESSMENT_RECOMMENDATIONS = {"approve", "approve_with_conditions", "reject", "refer"}
RISK_GRADES = {"low", "medium", "high", "critical"}
VOTE_DECISIONS = {"approve", "approve_with_conditions", "reject", "abstain"}
FINAL_DECISIONS = {"approved", "conditionally_approved", "rejected"}
BLOCKING_CONDITION_TYPES = {"pre_contract", "pre_disbursement"}
RESOLVED_CONDITION_STATUSES = {"satisfied", "waived"}


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid money amount: {value!r}") from exc


def _reference(prefix: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now:%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def _scope_case_query(db: Session, context: TenantContext):
    query = db.query(CreditCommitteeCase).filter(CreditCommitteeCase.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(CreditCommitteeCase.branch_id == context.branch_id)
    return query


def application_or_404(db: Session, context: TenantContext, application_id: UUID) -> DirectLoanApplication:
    query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.id == application_id,
        DirectLoanApplication.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(DirectLoanApplication.branch_id == context.branch_id)
    application = query.first()
    if not application:
        raise HTTPException(status_code=404, detail="Loan application was not found in the active company/branch scope")
    return application


def case_or_404(db: Session, context: TenantContext, case_id: UUID, *, lock: bool = False) -> CreditCommitteeCase:
    query = _scope_case_query(db, context).filter(CreditCommitteeCase.id == case_id)
    if lock:
        query = query.with_for_update()
    case = query.first()
    if not case:
        raise HTTPException(status_code=404, detail="Credit committee case was not found")
    return case


def _borrower_name(db: Session, borrower_id: UUID) -> str:
    row = (
        db.query(Person.first_name, Person.middle_name, Person.last_name, User.email)
        .join(User, User.id == Person.user_id)
        .join("borrower_profile")
        .filter_by(id=borrower_id)
        .first()
    )
    if row:
        values = [row[0], row[1], row[2]]
        name = " ".join(str(value) for value in values if value).strip()
        return name or str(row[3] or "Borrower")
    return "Borrower"


def _borrower_name_safe(db: Session, borrower_id: UUID) -> str:
    # Avoid depending on a relationship-name join in deployments with mapper
    # customisation; the explicit borrower/user/person join is deterministic.
    from database.models.borrower import Borrower

    row = (
        db.query(Person.first_name, Person.middle_name, Person.last_name, User.email)
        .join(User, User.id == Person.user_id)
        .join(Borrower, Borrower.user_id == User.id)
        .filter(Borrower.id == borrower_id)
        .first()
    )
    if not row:
        return "Borrower"
    name = " ".join(str(value) for value in row[:3] if value).strip()
    return name or str(row[3] or "Borrower")


def _event(db: Session, case: CreditCommitteeCase, event_type: str, actor_user_id: UUID | None, payload: dict[str, Any] | None = None) -> None:
    db.add(CreditCommitteeEvent(
        company_id=case.company_id,
        case_id=case.id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload=payload or {},
    ))


def _latest_affordability(db: Session, application: DirectLoanApplication) -> AffordabilityAssessment | None:
    if application.affordability_assessment_id:
        row = db.get(AffordabilityAssessment, application.affordability_assessment_id)
        if row and row.company_id == application.company_id:
            return row
    return (
        db.query(AffordabilityAssessment)
        .filter(
            AffordabilityAssessment.company_id == application.company_id,
            AffordabilityAssessment.application_id == application.id,
        )
        .order_by(AffordabilityAssessment.assessment_number.desc(), AffordabilityAssessment.created_at.desc())
        .first()
    )


def build_evidence_snapshot(db: Session, application: DirectLoanApplication) -> dict[str, Any]:
    affordability = _latest_affordability(db, application)
    kyc = db.query(BorrowerKYCProfile).filter(
        BorrowerKYCProfile.borrower_id == application.borrower_id,
    ).first()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.borrower_id == application.borrower_id,
    ).first()
    bureau = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.company_id == application.company_id,
            CreditBureauEnquiry.borrower_id == application.borrower_id,
            CreditBureauEnquiry.status == "completed",
        )
        .order_by(CreditBureauEnquiry.completed_at.desc())
        .first()
    )
    rules_decision = (
        db.query(CreditDecision)
        .filter(
            CreditDecision.company_id == application.company_id,
            CreditDecision.application_id == application.id,
        )
        .order_by(CreditDecision.created_at.desc())
        .first()
    )
    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == application.company_id,
        CDASPayrollProfile.borrower_id == application.borrower_id,
    ).first()
    debts = db.query(BorrowerDebtObligation).filter(
        BorrowerDebtObligation.borrower_id == application.borrower_id,
        BorrowerDebtObligation.status == "active",
    ).all()
    open_compliance = db.query(func.count(ComplianceCase.id)).filter(
        ComplianceCase.company_id == application.company_id,
        ComplianceCase.borrower_id == application.borrower_id,
        ComplianceCase.status.notin_(["cleared", "closed"]),
    ).scalar() or 0
    active_loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == application.company_id,
        ClientCompanyLoan.borrower_id == application.borrower_id,
        ClientCompanyLoan.status.in_(["active", "defaulted"]),
    ).all()

    active_exposure = sum((money(row.balance) for row in active_loans), Decimal("0"))
    debt_installments = sum((money(row.monthly_installment) for row in debts), Decimal("0"))
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "application": {
            "id": str(application.id),
            "reference": application.application_reference,
            "status": application.status,
            "channel": application.channel,
            "application_type": application.application_type,
            "requested_amount": str(money(application.requested_amount)),
            "term_count": int(application.term_count or 0),
            "repayment_type": application.repayment_type,
            "purpose": application.purpose,
            "cdas_collection_enabled": bool(application.cdas_collection_enabled),
            "credit_warning": application.credit_warning or {},
            "top_up_eligibility_snapshot": application.top_up_eligibility_snapshot or {},
        },
        "affordability": {
            "available": bool(affordability),
            "decision": affordability.decision if affordability else None,
            "verified_income": str(money(affordability.verified_income)) if affordability else "0.00",
            "household_expenses": str(money(affordability.household_expenses)) if affordability else "0.00",
            "existing_debt_installments": str(money(affordability.existing_debt_installments)) if affordability else str(money(debt_installments)),
            "dti_percent": str(affordability.dti_percent or 0) if affordability else None,
            "maximum_affordable_installment": str(money(affordability.maximum_affordable_installment)) if affordability else "0.00",
            "proposed_installment": str(money(affordability.proposed_installment)) if affordability else "0.00",
            "affordability_headroom": str(money(affordability.affordability_headroom)) if affordability else "0.00",
            "reasons": list(affordability.result_reasons or []) if affordability else [],
            "overridden": bool(affordability.overridden) if affordability else False,
            "override_decision": affordability.override_decision if affordability else None,
            "override_reason": affordability.override_reason if affordability else None,
        },
        "kyc": {
            "available": bool(kyc),
            "status": kyc.status if kyc else None,
            "identity_verified": bool(kyc.identity_verified) if kyc else False,
            "address_verified": bool(kyc.address_verified) if kyc else False,
            "sanctions_hit": bool(kyc.sanctions_hit) if kyc else False,
            "politically_exposed": bool(kyc.politically_exposed) if kyc else False,
            "adverse_media_hit": bool(kyc.adverse_media_hit) if kyc else False,
            "fraud_flag": bool(kyc.fraud_flag) if kyc else False,
            "dependants": int(kyc.dependants or 0) if kyc else 0,
        },
        "employment": {
            "available": bool(employment),
            "employment_status": employment.employment_status if employment else None,
            "employer_name": employment.employer_name if employment else None,
            "employee_number": employment.employee_number if employment else None,
            "contract_type": employment.contract_type if employment else None,
            "contract_expiry_date": employment.contract_expiry_date.isoformat() if employment and employment.contract_expiry_date else None,
            "verified_net_income": str(money(employment.verified_net_income)) if employment else "0.00",
            "verification_status": employment.verification_status if employment else None,
            "payslip_count": int(employment.payslip_count or 0) if employment else 0,
            "bank_statement_months": int(employment.bank_statement_months or 0) if employment else 0,
        },
        "credit_bureau": {
            "available": bool(bureau),
            "reference": bureau.enquiry_reference if bureau else None,
            "score": bureau.score if bureau else None,
            "risk_grade": bureau.risk_grade if bureau else None,
            "current_exposure": str(money(bureau.current_exposure)) if bureau else "0.00",
            "monthly_obligations": str(money(bureau.monthly_obligations)) if bureau else "0.00",
            "adverse_records": int(bureau.adverse_records or 0) if bureau else 0,
            "completed_at": bureau.completed_at.isoformat() if bureau and bureau.completed_at else None,
        },
        "rules_engine": {
            "available": bool(rules_decision),
            "reference": rules_decision.decision_reference if rules_decision else None,
            "decision": rules_decision.decision if rules_decision else None,
            "score": str(rules_decision.score or 0) if rules_decision else None,
            "reasons": list(rules_decision.reasons or []) if rules_decision else [],
            "conditions": list(rules_decision.conditions or []) if rules_decision else [],
            "override_decision": rules_decision.override_decision if rules_decision else None,
            "override_reason": rules_decision.override_reason if rules_decision else None,
        },
        "existing_debts": {
            "active_count": len(debts),
            "monthly_installments": str(money(debt_installments)),
            "balances": str(money(sum((money(row.current_balance) for row in debts), Decimal("0")))),
        },
        "existing_company_loans": {
            "active_or_defaulted_count": len(active_loans),
            "outstanding_exposure": str(money(active_exposure)),
            "defaulted_count": sum(1 for row in active_loans if str(getattr(row.status, "value", row.status)) == "defaulted"),
        },
        "compliance": {"open_case_count": int(open_compliance)},
        "cdas": {
            "profile_available": bool(payroll),
            "verified": bool(payroll.verified) if payroll else False,
            "employee_number": payroll.employee_number if payroll else None,
            "net_salary": str(money(payroll.net_salary)) if payroll else "0.00",
            "existing_deductions": str(money(payroll.existing_deductions)) if payroll else "0.00",
            "maximum_deduction_percent": str(payroll.maximum_deduction_percent or 0) if payroll else None,
        },
    }


def ensure_case(
    db: Session,
    context: TenantContext,
    application: DirectLoanApplication,
    *,
    actor_user_id: UUID | None = None,
) -> CreditCommitteeCase:
    existing = db.query(CreditCommitteeCase).filter(
        CreditCommitteeCase.company_id == context.company_id,
        CreditCommitteeCase.application_id == application.id,
    ).first()
    if existing:
        return existing
    if application.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="Only submitted or under-review applications can enter credit committee")
    case = CreditCommitteeCase(
        company_id=application.company_id,
        branch_id=application.branch_id,
        application_id=application.id,
        borrower_id=application.borrower_id,
        case_reference=_reference("CC"),
        status="underwriting",
        required_votes=2,
        approval_threshold_percent=Decimal("66.667"),
        maker_checker_required=True,
        evidence_snapshot=build_evidence_snapshot(db, application),
    )
    db.add(case)
    db.flush()
    _event(db, case, "case_opened", actor_user_id, {
        "application_reference": application.application_reference,
        "required_votes": 2,
        "approval_threshold_percent": "66.667",
        "maker_checker_required": True,
    })
    db.commit()
    db.refresh(case)
    return case


def _latest_assessment(db: Session, case_id: UUID) -> UnderwritingAssessment | None:
    return (
        db.query(UnderwritingAssessment)
        .filter(UnderwritingAssessment.case_id == case_id)
        .order_by(UnderwritingAssessment.revision.desc())
        .first()
    )


def _vote_summary_from_rows(case: CreditCommitteeCase, votes: list[CreditCommitteeVote]) -> dict[str, Any]:
    counts = {key: 0 for key in sorted(VOTE_DECISIONS)}
    for vote in votes:
        counts[vote.decision] = counts.get(vote.decision, 0) + 1
    decisive = counts.get("approve", 0) + counts.get("approve_with_conditions", 0) + counts.get("reject", 0)
    approve_like = counts.get("approve", 0) + counts.get("approve_with_conditions", 0)
    ratio = Decimal("0") if decisive <= 0 else (Decimal(approve_like) / Decimal(decisive) * Decimal("100")).quantize(Decimal("0.001"))
    quorum_met = decisive >= int(case.required_votes or 1)
    outcome: str | None = None
    if quorum_met:
        if ratio >= Decimal(case.approval_threshold_percent or 0):
            outcome = "conditionally_approved" if counts.get("approve_with_conditions", 0) else "approved"
        else:
            outcome = "rejected"
    return {
        "counts": counts,
        "decisive_vote_count": decisive,
        "approve_like_count": approve_like,
        "approval_ratio_percent": float(ratio),
        "required_votes": int(case.required_votes or 1),
        "approval_threshold_percent": float(case.approval_threshold_percent or 0),
        "quorum_met": quorum_met,
        "computed_outcome": outcome,
    }


def vote_summary(db: Session, case: CreditCommitteeCase) -> dict[str, Any]:
    votes = db.query(CreditCommitteeVote).filter(CreditCommitteeVote.case_id == case.id).all()
    return _vote_summary_from_rows(case, votes)


def assessment_payload(row: UnderwritingAssessment | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": str(row.id),
        "revision": row.revision,
        "status": row.status,
        "analyst_user_id": str(row.analyst_user_id) if row.analyst_user_id else None,
        "requested_amount": float(row.requested_amount or 0),
        "proposed_amount": float(row.proposed_amount or 0),
        "proposed_installment": float(row.proposed_installment or 0),
        "proposed_term": row.proposed_term,
        "verified_income": float(row.verified_income or 0),
        "household_expenses": float(row.household_expenses or 0),
        "existing_debt_installments": float(row.existing_debt_installments or 0),
        "dti_percent": float(row.dti_percent or 0),
        "affordability_headroom": float(row.affordability_headroom or 0),
        "bureau_score": row.bureau_score,
        "bureau_risk_grade": row.bureau_risk_grade,
        "kyc_status": row.kyc_status,
        "risk_score": float(row.risk_score) if row.risk_score is not None else None,
        "risk_grade": row.risk_grade,
        "recommendation": row.recommendation,
        "rationale": row.rationale,
        "strengths": list(row.strengths or []),
        "weaknesses": list(row.weaknesses or []),
        "exceptions": list(row.exceptions or []),
        "mitigants": list(row.mitigants or []),
        "proposed_conditions": list(row.proposed_conditions or []),
        "evidence_snapshot": row.evidence_snapshot or {},
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
    }


def vote_payload(row: CreditCommitteeVote) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "role": row.role,
        "decision": row.decision,
        "rationale": row.rationale,
        "conditions": list(row.conditions or []),
        "voted_at": row.voted_at.isoformat() if row.voted_at else None,
    }


def condition_payload(row: CreditCommitteeCondition) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source": row.source,
        "condition_type": row.condition_type,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "evidence_note": row.evidence_note,
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "resolved_by_user_id": str(row.resolved_by_user_id) if row.resolved_by_user_id else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "waiver_reason": row.waiver_reason,
    }


def case_payload(db: Session, case: CreditCommitteeCase, *, include_events: bool = False) -> dict[str, Any]:
    application = db.get(DirectLoanApplication, case.application_id)
    latest = _latest_assessment(db, case.id)
    votes = db.query(CreditCommitteeVote).filter(CreditCommitteeVote.case_id == case.id).order_by(CreditCommitteeVote.voted_at.asc()).all()
    conditions = db.query(CreditCommitteeCondition).filter(CreditCommitteeCondition.case_id == case.id).order_by(CreditCommitteeCondition.created_at.asc()).all()
    result = {
        "id": str(case.id),
        "case_reference": case.case_reference,
        "company_id": str(case.company_id),
        "branch_id": str(case.branch_id) if case.branch_id else None,
        "application_id": str(case.application_id),
        "application_reference": application.application_reference if application else None,
        "application_status": application.status if application else None,
        "borrower_id": str(case.borrower_id),
        "borrower_name": _borrower_name_safe(db, case.borrower_id),
        "requested_amount": float(application.requested_amount or 0) if application else 0,
        "term_count": int(application.term_count or 0) if application else 0,
        "application_type": application.application_type if application else None,
        "channel": application.channel if application else None,
        "status": case.status,
        "required_votes": case.required_votes,
        "approval_threshold_percent": float(case.approval_threshold_percent or 0),
        "maker_checker_required": bool(case.maker_checker_required),
        "analyst_user_id": str(case.analyst_user_id) if case.analyst_user_id else None,
        "analyst_submitted_at": case.analyst_submitted_at.isoformat() if case.analyst_submitted_at else None,
        "evidence_snapshot": case.evidence_snapshot or {},
        "latest_assessment": assessment_payload(latest),
        "votes": [vote_payload(row) for row in votes],
        "vote_summary": _vote_summary_from_rows(case, votes),
        "conditions": [condition_payload(row) for row in conditions],
        "final_decision": case.final_decision,
        "final_decision_reason": case.final_decision_reason,
        "final_decided_by_user_id": str(case.final_decided_by_user_id) if case.final_decided_by_user_id else None,
        "final_decided_at": case.final_decided_at.isoformat() if case.final_decided_at else None,
        "override_used": bool(case.override_used),
        "override_reason": case.override_reason,
        "locked_at": case.locked_at.isoformat() if case.locked_at else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }
    if include_events:
        events = db.query(CreditCommitteeEvent).filter(CreditCommitteeEvent.case_id == case.id).order_by(CreditCommitteeEvent.created_at.asc()).limit(250).all()
        result["events"] = [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "payload": row.payload or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in events
        ]
    return result


def dashboard_payload(db: Session, context: TenantContext) -> dict[str, Any]:
    cases = _scope_case_query(db, context).order_by(CreditCommitteeCase.created_at.desc()).limit(500).all()
    case_application_ids = {row.application_id for row in cases}
    intake_query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.company_id == context.company_id,
        DirectLoanApplication.credit_committee_required.is_(True),
        DirectLoanApplication.status.in_(["submitted", "under_review"]),
    )
    if context.branch_id:
        intake_query = intake_query.filter(DirectLoanApplication.branch_id == context.branch_id)
    awaiting = [row for row in intake_query.order_by(DirectLoanApplication.created_at.asc()).all() if row.id not in case_application_ids]
    return {
        "summary": {
            "awaiting_intake": len(awaiting),
            "underwriting": sum(row.status == "underwriting" for row in cases),
            "committee_review": sum(row.status == "committee_review" for row in cases),
            "awaiting_conditions": sum(row.status == "awaiting_conditions" for row in cases),
            "approved": sum(row.status == "approved" for row in cases),
            "rejected": sum(row.status == "rejected" for row in cases),
        },
        "awaiting_intake": [
            {
                "application_id": str(row.id),
                "application_reference": row.application_reference,
                "borrower_id": str(row.borrower_id),
                "borrower_name": _borrower_name_safe(db, row.borrower_id),
                "requested_amount": float(row.requested_amount or 0),
                "term_count": row.term_count,
                "status": row.status,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            }
            for row in awaiting
        ],
        "cases": [case_payload(db, row) for row in cases],
    }


def _decimal_from_snapshot(snapshot: dict[str, Any], path: tuple[str, ...], fallback: Decimal = Decimal("0")) -> Decimal:
    value: Any = snapshot
    for key in path:
        if not isinstance(value, dict):
            return fallback
        value = value.get(key)
    try:
        return Decimal(str(value or fallback))
    except InvalidOperation:
        return fallback


def submit_assessment(
    db: Session,
    context: TenantContext,
    case: CreditCommitteeCase,
    *,
    proposed_amount: Decimal | None,
    proposed_installment: Decimal | None,
    proposed_term: int | None,
    verified_income: Decimal | None,
    household_expenses: Decimal | None,
    existing_debt_installments: Decimal | None,
    dti_percent: Decimal | None,
    affordability_headroom: Decimal | None,
    bureau_score: int | None,
    bureau_risk_grade: str | None,
    risk_score: Decimal | None,
    risk_grade: str,
    recommendation: str,
    rationale: str,
    strengths: list[str],
    weaknesses: list[str],
    exceptions: list[str],
    mitigants: list[str],
    proposed_conditions: list[dict[str, Any]],
) -> UnderwritingAssessment:
    if case.locked_at:
        raise HTTPException(status_code=409, detail="The committee case is locked after final decision")
    if db.query(CreditCommitteeVote.id).filter(CreditCommitteeVote.case_id == case.id).first():
        raise HTTPException(status_code=409, detail="Committee voting has started. Reset the case before replacing the submitted credit memo.")
    recommendation = recommendation.strip().lower()
    risk_grade = risk_grade.strip().lower()
    if recommendation not in ASSESSMENT_RECOMMENDATIONS:
        raise HTTPException(status_code=422, detail="Invalid underwriting recommendation")
    if risk_grade not in RISK_GRADES:
        raise HTTPException(status_code=422, detail="Risk grade must be low, medium, high or critical")
    if not rationale.strip():
        raise HTTPException(status_code=422, detail="A written underwriting rationale is required")

    application = db.get(DirectLoanApplication, case.application_id)
    if not application:
        raise HTTPException(status_code=409, detail="The linked loan application no longer exists")
    snapshot = build_evidence_snapshot(db, application)
    latest = _latest_assessment(db, case.id)
    revision = int(latest.revision or 0) + 1 if latest else 1
    if latest:
        latest.status = "superseded"

    income = money(verified_income if verified_income is not None else _decimal_from_snapshot(snapshot, ("affordability", "verified_income")))
    expenses = money(household_expenses if household_expenses is not None else _decimal_from_snapshot(snapshot, ("affordability", "household_expenses")))
    debt = money(existing_debt_installments if existing_debt_installments is not None else _decimal_from_snapshot(snapshot, ("affordability", "existing_debt_installments")))
    installment = money(proposed_installment if proposed_installment is not None else _decimal_from_snapshot(snapshot, ("affordability", "proposed_installment")))
    amount = money(proposed_amount if proposed_amount is not None else application.requested_amount)
    if dti_percent is None:
        dti_value = Decimal("0") if income <= 0 else ((debt + installment) / income * Decimal("100")).quantize(Decimal("0.001"))
    else:
        dti_value = Decimal(str(dti_percent)).quantize(Decimal("0.001"))
    headroom = money(affordability_headroom if affordability_headroom is not None else _decimal_from_snapshot(snapshot, ("affordability", "affordability_headroom")))
    resolved_bureau_score = bureau_score if bureau_score is not None else snapshot.get("credit_bureau", {}).get("score")
    resolved_bureau_grade = bureau_risk_grade or snapshot.get("credit_bureau", {}).get("risk_grade")

    row = UnderwritingAssessment(
        company_id=case.company_id,
        case_id=case.id,
        application_id=case.application_id,
        borrower_id=case.borrower_id,
        revision=revision,
        status="submitted",
        analyst_user_id=context.user.id,
        requested_amount=money(application.requested_amount),
        proposed_amount=amount,
        proposed_installment=installment,
        proposed_term=int(proposed_term or application.term_count or 0),
        verified_income=income,
        household_expenses=expenses,
        existing_debt_installments=debt,
        dti_percent=dti_value,
        affordability_headroom=headroom,
        bureau_score=resolved_bureau_score,
        bureau_risk_grade=resolved_bureau_grade,
        kyc_status=snapshot.get("kyc", {}).get("status"),
        risk_score=Decimal(str(risk_score)).quantize(Decimal("0.001")) if risk_score is not None else None,
        risk_grade=risk_grade,
        recommendation=recommendation,
        rationale=rationale.strip(),
        strengths=[item.strip() for item in strengths if item.strip()],
        weaknesses=[item.strip() for item in weaknesses if item.strip()],
        exceptions=[item.strip() for item in exceptions if item.strip()],
        mitigants=[item.strip() for item in mitigants if item.strip()],
        proposed_conditions=proposed_conditions,
        evidence_snapshot=snapshot,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    case.analyst_user_id = context.user.id
    case.analyst_submitted_at = row.submitted_at
    case.evidence_snapshot = snapshot
    case.status = "committee_review"
    _event(db, case, "underwriting_submitted", context.user.id, {
        "revision": revision,
        "recommendation": recommendation,
        "risk_grade": risk_grade,
        "proposed_amount": str(amount),
        "proposed_installment": str(installment),
        "dti_percent": str(dti_value),
        "exceptions": row.exceptions,
        "proposed_conditions": proposed_conditions,
    })
    db.commit()
    db.refresh(row)
    return row


def cast_vote(
    db: Session,
    context: TenantContext,
    case: CreditCommitteeCase,
    *,
    decision: str,
    rationale: str,
    conditions: list[dict[str, Any]],
) -> CreditCommitteeVote:
    if case.locked_at or case.final_decision:
        raise HTTPException(status_code=409, detail="Voting is closed because the case has a final decision")
    if case.status != "committee_review":
        raise HTTPException(status_code=409, detail="An analyst credit memo must be submitted before committee voting")
    if case.maker_checker_required and case.analyst_user_id == context.user.id:
        raise HTTPException(status_code=409, detail="Maker-checker control prevents the underwriting analyst from voting on the same case")
    decision = decision.strip().lower()
    if decision not in VOTE_DECISIONS:
        raise HTTPException(status_code=422, detail="Invalid committee vote")
    if decision != "abstain" and not rationale.strip():
        raise HTTPException(status_code=422, detail="A rationale is required for a committee vote")
    if decision == "approve_with_conditions" and not conditions:
        raise HTTPException(status_code=422, detail="An approval with conditions must state at least one condition")

    row = db.query(CreditCommitteeVote).filter(
        CreditCommitteeVote.case_id == case.id,
        CreditCommitteeVote.user_id == context.user.id,
    ).first()
    previous = vote_payload(row) if row else None
    if not row:
        row = CreditCommitteeVote(
            company_id=case.company_id,
            case_id=case.id,
            user_id=context.user.id,
        )
        db.add(row)
    row.role = context.role.value
    row.decision = decision
    row.rationale = rationale.strip() or "Abstained"
    row.conditions = conditions
    row.voted_at = datetime.now(timezone.utc)
    db.flush()
    _event(db, case, "committee_vote_recorded", context.user.id, {
        "previous": previous,
        "current": vote_payload(row),
    })
    db.commit()
    db.refresh(row)
    return row


def _condition_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("condition_type") or "pre_disbursement").strip().lower(), str(item.get("title") or "").strip().lower())


def _collect_decision_conditions(assessment: UnderwritingAssessment | None, votes: list[CreditCommitteeVote]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for raw in list(assessment.proposed_conditions or []) if assessment else []:
        if isinstance(raw, str):
            candidates.append({"title": raw, "condition_type": "pre_disbursement"})
        elif isinstance(raw, dict):
            candidates.append(dict(raw))
    for vote in votes:
        if vote.decision != "approve_with_conditions":
            continue
        for raw in list(vote.conditions or []):
            if isinstance(raw, str):
                candidates.append({"title": raw, "condition_type": "pre_disbursement"})
            elif isinstance(raw, dict):
                candidates.append(dict(raw))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        condition_type = str(item.get("condition_type") or "pre_disbursement").strip().lower()
        if condition_type not in {"pre_contract", "pre_disbursement", "monitoring"}:
            condition_type = "pre_disbursement"
        normalized = {
            "title": title,
            "description": str(item.get("description") or "").strip() or None,
            "condition_type": condition_type,
            "due_date": item.get("due_date"),
        }
        unique[_condition_key(normalized)] = normalized
    return list(unique.values())


def finalize_case(
    db: Session,
    context: TenantContext,
    case: CreditCommitteeCase,
    *,
    reason: str | None,
    requested_decision: str | None,
    override_reason: str | None,
    allow_override: bool,
) -> CreditCommitteeCase:
    if case.locked_at or case.final_decision:
        raise HTTPException(status_code=409, detail="The committee case already has a final decision")
    if case.status != "committee_review":
        raise HTTPException(status_code=409, detail="The case is not ready for final committee decision")
    assessment = _latest_assessment(db, case.id)
    if not assessment or assessment.status != "submitted":
        raise HTTPException(status_code=409, detail="A submitted underwriting assessment is required")
    votes = db.query(CreditCommitteeVote).filter(CreditCommitteeVote.case_id == case.id).order_by(CreditCommitteeVote.voted_at.asc()).all()
    summary = _vote_summary_from_rows(case, votes)
    if not summary["quorum_met"]:
        raise HTTPException(status_code=409, detail=f"Committee quorum is not met: {summary['decisive_vote_count']} decisive vote(s), {summary['required_votes']} required")
    computed = summary["computed_outcome"]
    decision = (requested_decision or computed or "").strip().lower()
    if decision not in FINAL_DECISIONS:
        raise HTTPException(status_code=422, detail="Final decision must be approved, conditionally_approved or rejected")
    override_used = decision != computed
    if override_used:
        if not allow_override:
            raise HTTPException(status_code=403, detail="Only company management may override the computed committee outcome")
        if not (override_reason or "").strip():
            raise HTTPException(status_code=422, detail="A documented override reason is required when changing the computed committee outcome")

    conditions = _collect_decision_conditions(assessment, votes) if decision == "conditionally_approved" else []
    for item in conditions:
        due_date = item.get("due_date")
        db.add(CreditCommitteeCondition(
            company_id=case.company_id,
            case_id=case.id,
            source="committee",
            condition_type=item["condition_type"],
            title=item["title"],
            description=item.get("description"),
            due_date=due_date or None,
            status="open",
            created_by_user_id=context.user.id,
        ))

    now = datetime.now(timezone.utc)
    case.final_decision = decision
    case.final_decision_reason = (reason or "").strip() or assessment.rationale
    case.final_decided_by_user_id = context.user.id
    case.final_decided_at = now
    case.override_used = override_used
    case.override_reason = (override_reason or "").strip() or None
    case.locked_at = now
    case.status = "rejected" if decision == "rejected" else "awaiting_conditions" if conditions else "approved"
    case.final_snapshot = {
        "committee_summary": summary,
        "computed_outcome": computed,
        "final_decision": decision,
        "override_used": override_used,
        "override_reason": case.override_reason,
        "assessment_revision": assessment.revision,
        "assessment_recommendation": assessment.recommendation,
        "votes": [vote_payload(row) for row in votes],
        "conditions": conditions,
        "evidence_captured_at": (case.evidence_snapshot or {}).get("captured_at"),
    }
    _event(db, case, "committee_finalized", context.user.id, case.final_snapshot)

    application = db.get(DirectLoanApplication, case.application_id)
    if application and decision == "rejected":
        application.status = "rejected"
        application.rejected_at = now
        application.rejected_by_user_id = context.user.id
        application.decision_notes = case.final_decision_reason
    db.commit()
    db.refresh(case)
    return case


def update_condition(
    db: Session,
    context: TenantContext,
    case: CreditCommitteeCase,
    condition_id: UUID,
    *,
    status: str,
    evidence_note: str | None,
    waiver_reason: str | None,
) -> CreditCommitteeCondition:
    row = db.query(CreditCommitteeCondition).filter(
        CreditCommitteeCondition.id == condition_id,
        CreditCommitteeCondition.case_id == case.id,
        CreditCommitteeCondition.company_id == context.company_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Credit condition was not found")
    status = status.strip().lower()
    if status not in {"open", "satisfied", "waived", "failed"}:
        raise HTTPException(status_code=422, detail="Invalid credit-condition status")
    if status == "satisfied" and not (evidence_note or "").strip():
        raise HTTPException(status_code=422, detail="Evidence notes are required before satisfying a credit condition")
    if status == "waived" and not (waiver_reason or "").strip():
        raise HTTPException(status_code=422, detail="A waiver reason is required")
    previous = row.status
    row.status = status
    row.evidence_note = (evidence_note or "").strip() or row.evidence_note
    row.waiver_reason = (waiver_reason or "").strip() or None
    if status in RESOLVED_CONDITION_STATUSES:
        row.resolved_by_user_id = context.user.id
        row.resolved_at = datetime.now(timezone.utc)
    else:
        row.resolved_by_user_id = None
        row.resolved_at = None
    _event(db, case, "condition_updated", context.user.id, {
        "condition_id": str(row.id),
        "title": row.title,
        "previous_status": previous,
        "status": status,
        "evidence_note": row.evidence_note,
        "waiver_reason": row.waiver_reason,
    })
    db.flush()
    if case.final_decision == "conditionally_approved":
        blocking = db.query(CreditCommitteeCondition).filter(
            CreditCommitteeCondition.case_id == case.id,
            CreditCommitteeCondition.condition_type.in_(list(BLOCKING_CONDITION_TYPES)),
            CreditCommitteeCondition.status.notin_(list(RESOLVED_CONDITION_STATUSES)),
        ).count()
        case.status = "awaiting_conditions" if blocking else "approved"
    db.commit()
    db.refresh(row)
    return row


def configure_case_governance(
    db: Session,
    context: TenantContext,
    case: CreditCommitteeCase,
    *,
    required_votes: int,
    approval_threshold_percent: Decimal,
    maker_checker_required: bool,
    reason: str,
) -> CreditCommitteeCase:
    if case.locked_at or db.query(CreditCommitteeVote.id).filter(CreditCommitteeVote.case_id == case.id).first():
        raise HTTPException(status_code=409, detail="Committee governance cannot change after voting begins")
    if required_votes < 1 or required_votes > 20:
        raise HTTPException(status_code=422, detail="Required votes must be between 1 and 20")
    threshold = Decimal(str(approval_threshold_percent))
    if threshold <= 0 or threshold > 100:
        raise HTTPException(status_code=422, detail="Approval threshold must be greater than 0 and no more than 100")
    if (required_votes < 2 or not maker_checker_required) and not reason.strip():
        raise HTTPException(status_code=422, detail="A governance reason is required when weakening the default maker-checker controls")
    before = {
        "required_votes": case.required_votes,
        "approval_threshold_percent": str(case.approval_threshold_percent),
        "maker_checker_required": case.maker_checker_required,
    }
    case.required_votes = required_votes
    case.approval_threshold_percent = threshold.quantize(Decimal("0.001"))
    case.maker_checker_required = maker_checker_required
    _event(db, case, "committee_governance_changed", context.user.id, {
        "before": before,
        "after": {
            "required_votes": required_votes,
            "approval_threshold_percent": str(case.approval_threshold_percent),
            "maker_checker_required": maker_checker_required,
        },
        "reason": reason.strip(),
    })
    db.commit()
    db.refresh(case)
    return case


def assert_application_committee_clearance(db: Session, application: DirectLoanApplication) -> CreditCommitteeCase | None:
    if not bool(getattr(application, "credit_committee_required", False)):
        return None
    case = db.query(CreditCommitteeCase).filter(
        CreditCommitteeCase.company_id == application.company_id,
        CreditCommitteeCase.application_id == application.id,
    ).first()
    if not case or case.final_decision not in {"approved", "conditionally_approved"}:
        raise HTTPException(status_code=409, detail="Credit Committee approval is required before this application can be converted to a loan")
    open_pre_contract = db.query(CreditCommitteeCondition).filter(
        CreditCommitteeCondition.case_id == case.id,
        CreditCommitteeCondition.condition_type == "pre_contract",
        CreditCommitteeCondition.status.notin_(list(RESOLVED_CONDITION_STATUSES)),
    ).count()
    if open_pre_contract:
        raise HTTPException(status_code=409, detail=f"{open_pre_contract} pre-contract Credit Committee condition(s) must be satisfied or formally waived before loan approval")
    return case


def assert_application_committee_rejection(db: Session, application: DirectLoanApplication) -> CreditCommitteeCase | None:
    if not bool(getattr(application, "credit_committee_required", False)):
        return None
    case = db.query(CreditCommitteeCase).filter(
        CreditCommitteeCase.company_id == application.company_id,
        CreditCommitteeCase.application_id == application.id,
    ).first()
    if not case or case.final_decision != "rejected":
        raise HTTPException(status_code=409, detail="A Credit Committee rejection is required before rejecting this governed application")
    return case


def assert_loan_disbursement_conditions(db: Session, loan: ClientCompanyLoan) -> None:
    if not loan.direct_application_id:
        return
    application = db.get(DirectLoanApplication, loan.direct_application_id)
    if not application or not bool(getattr(application, "credit_committee_required", False)):
        return
    case = db.query(CreditCommitteeCase).filter(
        CreditCommitteeCase.company_id == loan.company_id,
        CreditCommitteeCase.application_id == application.id,
    ).first()
    if not case or case.final_decision not in {"approved", "conditionally_approved"}:
        raise HTTPException(status_code=409, detail="Credit Committee clearance is missing for this loan")
    open_conditions = db.query(CreditCommitteeCondition).filter(
        CreditCommitteeCondition.case_id == case.id,
        CreditCommitteeCondition.condition_type.in_(["pre_contract", "pre_disbursement"]),
        CreditCommitteeCondition.status.notin_(list(RESOLVED_CONDITION_STATUSES)),
    ).all()
    if open_conditions:
        titles = ", ".join(row.title for row in open_conditions[:5])
        raise HTTPException(status_code=409, detail=f"Credit Committee conditions must be cleared before disbursement: {titles}")
