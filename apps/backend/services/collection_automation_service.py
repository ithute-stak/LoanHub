from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.collection_automation import (
    CollectionAutomationRun,
    CollectionTreatmentPolicy,
    CollectionWorkItem,
)
from database.models.employer_payroll import EmployerPayrollAccount
from database.models.lending_operations import (
    CDASDeductionMandate,
    CollectionActivity,
    CollectionCase,
)
from database.models.origination import BorrowerKYCProfile
from database.models.user import User
from services.lending_operations_service import sync_overdue_collection_cases


DEFAULT_STRATEGY = {
    "bands": [
        {"min_dpd": 1, "max_dpd": 7, "stage": "early_arrears", "action": "call", "treatment": "EARLY_CONTACT", "due_hours": 4},
        {"min_dpd": 8, "max_dpd": 30, "stage": "intensive_recovery", "action": "call", "treatment": "INTENSIVE_CONTACT", "due_hours": 2},
        {"min_dpd": 31, "max_dpd": 60, "stage": "late_arrears", "action": "default_notice", "treatment": "FORMAL_DEFAULT", "due_hours": 2},
        {"min_dpd": 61, "max_dpd": 99999, "stage": "pre_legal", "action": "legal_review", "treatment": "LEGAL_READINESS", "due_hours": 1},
    ],
    "broken_promise_action": "call",
    "broken_promise_treatment": "BROKEN_PROMISE",
    "broken_promise_due_hours": 1,
}


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_or_create_policy(db: Session, context: TenantContext) -> CollectionTreatmentPolicy:
    row = db.query(CollectionTreatmentPolicy).filter(
        CollectionTreatmentPolicy.company_id == context.company_id,
        CollectionTreatmentPolicy.is_active.is_(True),
    ).order_by(CollectionTreatmentPolicy.version.desc()).first()
    if row:
        return row
    row = CollectionTreatmentPolicy(
        company_id=context.company_id,
        name="LoanHub default collections strategy",
        version=1,
        strategy=DEFAULT_STRATEGY,
        configured_by_user_id=context.user.id,
    )
    db.add(row)
    db.flush()
    return row


def update_policy(db: Session, context: TenantContext, strategy: dict[str, Any]) -> CollectionTreatmentPolicy:
    if not isinstance(strategy.get("bands"), list) or not strategy["bands"]:
        raise HTTPException(status_code=422, detail="Treatment strategy requires at least one DPD band")
    for band in strategy["bands"]:
        for key in ("min_dpd", "max_dpd", "stage", "action", "treatment"):
            if key not in band:
                raise HTTPException(status_code=422, detail=f"Each DPD band requires {key}")
        if int(band["min_dpd"]) < 1 or int(band["max_dpd"]) < int(band["min_dpd"]):
            raise HTTPException(status_code=422, detail="Invalid DPD range in treatment strategy")
    current = get_or_create_policy(db, context)
    current.is_active = False
    row = CollectionTreatmentPolicy(
        company_id=context.company_id,
        name=current.name,
        version=current.version + 1,
        strategy=strategy,
        configured_by_user_id=context.user.id,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _band(strategy: dict[str, Any], dpd: int) -> dict[str, Any]:
    for item in strategy.get("bands") or []:
        if int(item.get("min_dpd", 0)) <= dpd <= int(item.get("max_dpd", 0)):
            return item
    return DEFAULT_STRATEGY["bands"][-1]


def _recovery_path(db: Session, case: CollectionCase, loan: ClientCompanyLoan, borrower: Borrower | None) -> str:
    if loan.cdas_collection_enabled:
        active = db.query(CDASDeductionMandate.id).filter(
            CDASDeductionMandate.company_id == case.company_id,
            CDASDeductionMandate.loan_id == loan.id,
            CDASDeductionMandate.status.in_(["submitted", "active"]),
        ).first()
        return "cdas_recovery" if active else "cdas_registration_review"
    if borrower and borrower.employer_group_id:
        account = db.query(EmployerPayrollAccount.id).filter(
            EmployerPayrollAccount.company_id == case.company_id,
            EmployerPayrollAccount.employer_group_id == borrower.employer_group_id,
            EmployerPayrollAccount.is_active.is_(True),
        ).first()
        if account:
            return "employer_payroll_recovery"
    return "direct_collection"


def legal_readiness(db: Session, case: CollectionCase) -> dict[str, Any]:
    loan = db.get(ClientCompanyLoan, case.loan_id)
    kyc = db.query(BorrowerKYCProfile).filter(BorrowerKYCProfile.borrower_id == case.borrower_id).first()
    activities = db.query(CollectionActivity).filter(CollectionActivity.case_id == case.id).all()
    types = {row.activity_type for row in activities}
    contact_attempts = sum(row.activity_type in {"call", "visit"} for row in activities)
    checks = {
        "loan_identified": bool(loan and loan.loan_reference),
        "borrower_identity_verified": bool(kyc and kyc.identity_verified),
        "borrower_address_verified": bool(kyc and kyc.address_verified),
        "default_notice_recorded": "default_notice" in types,
        "recovery_contact_attempted": contact_attempts > 0,
        "positive_outstanding_balance": bool(loan and _money(loan.balance) > 0),
        "material_delinquency": int(case.days_past_due or 0) >= 31,
    }
    missing = [key for key, value in checks.items() if not value]
    return {
        "ready": not missing,
        "checks": checks,
        "missing": missing,
        "contact_attempts": contact_attempts,
    }


def _priority(case: CollectionCase, *, broken_promise: bool, recovery_path: str) -> tuple[Decimal, str]:
    dpd = max(int(case.days_past_due or 0), 0)
    overdue = _money(case.overdue_amount)
    score = Decimal(dpd) * Decimal("1.5") + min(overdue / Decimal("100"), Decimal("100"))
    if broken_promise:
        score += Decimal("35")
    if recovery_path in {"cdas_registration_review", "employer_payroll_recovery"}:
        score += Decimal("8")
    if case.priority == "urgent":
        score += Decimal("20")
    if score >= 100:
        label = "urgent"
    elif score >= 60:
        label = "high"
    elif score < 20:
        label = "low"
    else:
        label = "normal"
    return score.quantize(Decimal("0.001")), label


def run_automation(db: Session, context: TenantContext) -> CollectionAutomationRun:
    started = datetime.now(timezone.utc)
    sync_overdue_collection_cases(db, context.company_id)
    policy = get_or_create_policy(db, context)
    strategy = dict(policy.strategy or DEFAULT_STRATEGY)
    query = db.query(CollectionCase).filter(
        CollectionCase.company_id == context.company_id,
        CollectionCase.status.notin_(["closed", "recovered", "written_off"]),
    )
    if context.branch_id:
        query = query.filter(CollectionCase.branch_id == context.branch_id)
    cases = query.all()
    created = updated = broken_count = ready_count = 0
    path_counts: dict[str, int] = defaultdict(int)
    now = datetime.now(timezone.utc)

    for case in cases:
        loan = db.get(ClientCompanyLoan, case.loan_id)
        borrower = db.get(Borrower, case.borrower_id)
        if not loan:
            continue
        dpd = max(int(case.days_past_due or 0), 0)
        broken = bool(
            case.promise_date
            and case.promise_date < now.date()
            and (case.promise_status or "pending") not in {"kept", "paid", "cancelled"}
            and _money(case.overdue_amount) > 0
        )
        if broken and case.promise_status != "broken":
            case.promise_status = "broken"
            broken_count += 1

        band = _band(strategy, dpd)
        case.stage = str(band.get("stage") or case.stage)
        recovery_path = _recovery_path(db, case, loan, borrower)
        path_counts[recovery_path] += 1
        score, priority = _priority(case, broken_promise=broken, recovery_path=recovery_path)
        case.priority = priority

        if broken:
            action = str(strategy.get("broken_promise_action") or "call")
            treatment = str(strategy.get("broken_promise_treatment") or "BROKEN_PROMISE")
            due_hours = int(strategy.get("broken_promise_due_hours") or 1)
            reason = "Promise-to-pay date passed while the account remains overdue."
        else:
            action = str(band.get("action") or "call")
            treatment = str(band.get("treatment") or "STANDARD")
            due_hours = int(band.get("due_hours") or 4)
            reason = f"{dpd} day(s) past due; treatment band {treatment}."

        due_at = now + timedelta(hours=max(due_hours, 0))
        dedup = f"{treatment}:{now.date().isoformat()}"
        item = db.query(CollectionWorkItem).filter(
            CollectionWorkItem.case_id == case.id,
            CollectionWorkItem.deduplication_key == dedup,
        ).first()
        snapshot = {
            "days_past_due": dpd,
            "overdue_amount": str(_money(case.overdue_amount)),
            "outstanding_balance": str(_money(case.outstanding_balance)),
            "promise_status": case.promise_status,
            "promise_date": case.promise_date.isoformat() if case.promise_date else None,
            "recovery_path": recovery_path,
            "loan_reference": loan.loan_reference,
            "folio_number": loan.folio_number,
        }
        if not item:
            item = CollectionWorkItem(
                company_id=case.company_id,
                branch_id=case.branch_id,
                case_id=case.id,
                loan_id=case.loan_id,
                borrower_id=case.borrower_id,
                assigned_to_user_id=case.assigned_to_user_id,
                deduplication_key=dedup,
                action_type=action,
                treatment_code=treatment,
                recovery_path=recovery_path,
                priority_score=score,
                priority=priority,
                reason=reason,
                due_at=due_at,
                context_snapshot=snapshot,
            )
            db.add(item)
            created += 1
        elif item.status in {"open", "in_progress"}:
            item.priority_score = score
            item.priority = priority
            item.recovery_path = recovery_path
            item.context_snapshot = snapshot
            item.assigned_to_user_id = case.assigned_to_user_id
            updated += 1
        readiness = legal_readiness(db, case)
        if readiness["ready"]:
            ready_count += 1

    completed = datetime.now(timezone.utc)
    run = CollectionAutomationRun(
        company_id=context.company_id,
        branch_id=context.branch_id,
        run_reference=f"CAR-{completed:%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}",
        cases_checked=len(cases),
        work_items_created=created,
        work_items_updated=updated,
        broken_promises_detected=broken_count,
        legal_ready_cases=ready_count,
        summary={"recovery_paths": dict(path_counts), "policy_version": policy.version},
        started_at=started,
        completed_at=completed,
        triggered_by_user_id=context.user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def work_item_payload(db: Session, item: CollectionWorkItem) -> dict[str, Any]:
    case = db.get(CollectionCase, item.case_id)
    loan = db.get(ClientCompanyLoan, item.loan_id)
    borrower = db.get(Borrower, item.borrower_id)
    user = db.get(User, item.assigned_to_user_id) if item.assigned_to_user_id else None
    return {
        "id": str(item.id),
        "case_id": str(item.case_id),
        "case_reference": case.case_reference if case else None,
        "loan_id": str(item.loan_id),
        "loan_reference": loan.loan_reference if loan else None,
        "folio_number": loan.folio_number if loan else None,
        "borrower_id": str(item.borrower_id),
        "borrower_email": borrower.user.email if borrower and borrower.user else None,
        "assigned_to_user_id": str(item.assigned_to_user_id) if item.assigned_to_user_id else None,
        "assigned_to": user.email if user else None,
        "action_type": item.action_type,
        "treatment_code": item.treatment_code,
        "recovery_path": item.recovery_path,
        "priority_score": float(item.priority_score or 0),
        "priority": item.priority,
        "reason": item.reason,
        "due_at": item.due_at.isoformat(),
        "status": item.status,
        "attempt_count": item.attempt_count,
        "context_snapshot": dict(item.context_snapshot or {}),
    }


def dashboard(db: Session, context: TenantContext) -> dict[str, Any]:
    query = db.query(CollectionWorkItem).filter(CollectionWorkItem.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(CollectionWorkItem.branch_id == context.branch_id)
    items = query.filter(CollectionWorkItem.status.in_(["open", "in_progress"])).order_by(
        CollectionWorkItem.priority_score.desc(), CollectionWorkItem.due_at.asc()
    ).limit(1000).all()
    now = datetime.now(timezone.utc)
    paths: dict[str, int] = defaultdict(int)
    for item in items:
        paths[item.recovery_path] += 1

    case_query = db.query(CollectionCase).filter(CollectionCase.company_id == context.company_id)
    if context.branch_id:
        case_query = case_query.filter(CollectionCase.branch_id == context.branch_id)
    cases = case_query.all()
    broken = sum(case.promise_status == "broken" for case in cases)
    legal_ready = sum(legal_readiness(db, case)["ready"] for case in cases if case.status not in {"closed", "recovered"})

    activity_query = db.query(CollectionActivity).join(CollectionCase, CollectionCase.id == CollectionActivity.case_id).filter(
        CollectionActivity.company_id == context.company_id
    )
    if context.branch_id:
        activity_query = activity_query.filter(CollectionCase.branch_id == context.branch_id)
    activities = activity_query.all()
    productivity: dict[str, dict[str, Any]] = defaultdict(lambda: {"actions": 0, "promises": 0, "recovered": Decimal("0")})
    for row in activities:
        key = str(row.performed_by_user_id or "unassigned")
        productivity[key]["actions"] += 1
        if row.activity_type == "promise_to_pay":
            productivity[key]["promises"] += 1
        if row.amount and row.outcome in {"paid", "recovered", "settled"}:
            productivity[key]["recovered"] += _money(row.amount)
    people = []
    for user_id, values in productivity.items():
        user = db.get(User, user_id) if user_id != "unassigned" else None
        people.append({
            "user_id": user_id if user else None,
            "name": user.email if user else "Unassigned",
            "actions": values["actions"],
            "promises": values["promises"],
            "recovered": float(values["recovered"]),
        })
    people.sort(key=lambda row: (row["recovered"], row["actions"]), reverse=True)
    return {
        "summary": {
            "open_work_items": len(items),
            "urgent_work_items": sum(item.priority == "urgent" for item in items),
            "overdue_work_items": sum(item.due_at < now for item in items),
            "broken_promises": broken,
            "legal_ready_cases": legal_ready,
            "total_overdue": float(sum((_money(case.overdue_amount) for case in cases), Decimal("0"))),
        },
        "recovery_paths": dict(paths),
        "queue": [work_item_payload(db, item) for item in items],
        "productivity": people,
    }


def complete_work_item(db: Session, context: TenantContext, item: CollectionWorkItem, notes: str | None) -> CollectionWorkItem:
    if item.company_id != context.company_id:
        raise HTTPException(status_code=404, detail="Collection work item not found")
    if item.status == "completed":
        return item
    item.status = "completed"
    item.completed_at = datetime.now(timezone.utc)
    item.completed_by_user_id = context.user.id
    item.completion_notes = (notes or "").strip() or None
    db.commit()
    db.refresh(item)
    return item
