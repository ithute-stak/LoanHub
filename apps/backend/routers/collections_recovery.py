from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from database.config.config import settings
from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_user_context,
)
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.company_client_case import CompanyClientCaseEntry
from database.models.enums import UserRole
from database.models.file_management import ManagedFile
from database.models.lending_operations import CollectionActivity, CollectionCase
from database.models.origination import BorrowerBankAccount, BorrowerKYCProfile
from database.models.reporting import GeneratedReport
from database.models.repayment import RepaymentInstallment
from database.schemas.file_management import ManagedFileRead
from database.session import get_db
from services.collection_daily_reporting_service import (
    REPORT_TYPE,
    _borrower_snapshot,
    generate_company_reports,
)
from services.file_service import save_upload
from services.lending_operations_service import sync_overdue_collection_cases
from services.maturity_recovery_service import assert_or_claim_collection_case, release_collection_case_claim

router = APIRouter(prefix="/collections", tags=["Collections and Recoveries"])

VIEW_ROLES = COMPANY_MANAGEMENT_ROLES | COLLECTIONS_ROLES | {
    UserRole.AUDITOR,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.RISK_MANAGER,
}
ACTION_ROLES = COMPANY_MANAGEMENT_ROLES | COLLECTIONS_ROLES


def _company_id(context: TenantContext, roles: set[UserRole]) -> UUID:
    if context.is_platform_admin:
        raise HTTPException(status_code=400, detail="Select a company-scoped role for collections")
    if not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company membership is required")
    if context.role not in roles:
        raise HTTPException(status_code=403, detail="The active role is not allowed to perform this collection operation")
    return context.company_id


def _case_or_404(db: Session, context: TenantContext, case_id: UUID) -> CollectionCase:
    company_id = _company_id(context, VIEW_ROLES)
    case = db.query(CollectionCase).filter(
        CollectionCase.id == case_id,
        CollectionCase.company_id == company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Collection case not found")
    if context.branch_id and case.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Collection case is outside the active branch")
    return case


def _document_payload(file: ManagedFile) -> dict[str, Any]:
    return ManagedFileRead.model_validate(file).model_dump(mode="json")


def _documents_for_activity(db: Session, activity_id: UUID) -> list[dict[str, Any]]:
    rows = db.query(ManagedFile).filter(
        ManagedFile.linked_entity_type == "collection_activity",
        ManagedFile.linked_entity_id == str(activity_id),
        ManagedFile.is_deleted.is_(False),
    ).order_by(ManagedFile.created_at.asc()).all()
    return [_document_payload(item) for item in rows]


def _activity_payload(db: Session, row: CollectionActivity) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "company_id": str(row.company_id),
        "activity_type": row.activity_type,
        "outcome": row.outcome,
        "notes": row.notes,
        "amount": float(row.amount) if row.amount is not None else None,
        "follow_up_at": row.follow_up_at.isoformat() if row.follow_up_at else None,
        "performed_at": row.performed_at.isoformat() if row.performed_at else None,
        "performed_by_user_id": str(row.performed_by_user_id) if row.performed_by_user_id else None,
        "metadata_json": dict(row.metadata_json or {}),
        "documents": _documents_for_activity(db, row.id),
    }


def _case_payload(db: Session, case: CollectionCase) -> dict[str, Any]:
    loan = db.get(ClientCompanyLoan, case.loan_id)
    if not loan:
        return {
            "id": str(case.id),
            "case_reference": case.case_reference,
            "missing_loan": True,
        }
    snapshot = _borrower_snapshot(db, loan)
    overdue_rows = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.loan_id == loan.id,
        RepaymentInstallment.is_superseded.is_(False),
        RepaymentInstallment.paid_amount < RepaymentInstallment.total_due,
        RepaymentInstallment.due_date < datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date(),
    ).order_by(RepaymentInstallment.due_date.asc()).all()
    earliest = overdue_rows[0] if overdue_rows else None
    last_action = db.query(CollectionActivity).filter(
        CollectionActivity.case_id == case.id,
    ).order_by(CollectionActivity.performed_at.desc()).first()
    return {
        "id": str(case.id),
        "company_id": str(case.company_id),
        "branch_id": str(case.branch_id) if case.branch_id else None,
        "borrower_id": str(case.borrower_id),
        "loan_id": str(case.loan_id),
        "case_reference": case.case_reference,
        "status": case.status,
        "stage": case.stage,
        "days_past_due": case.days_past_due,
        "overdue_amount": float(case.overdue_amount or 0),
        "outstanding_balance": float(case.outstanding_balance or 0),
        "priority": case.priority,
        "next_action_at": case.next_action_at.isoformat() if case.next_action_at else None,
        "last_contact_at": case.last_contact_at.isoformat() if case.last_contact_at else None,
        "legal_handover_at": case.legal_handover_at.isoformat() if case.legal_handover_at else None,
        "assigned_to_user_id": str(case.assigned_to_user_id) if case.assigned_to_user_id else None,
        "action_claimed_by_user_id": str(case.action_claimed_by_user_id) if case.action_claimed_by_user_id else None,
        "action_claimed_at": case.action_claimed_at.isoformat() if case.action_claimed_at else None,
        "action_claim_expires_at": case.action_claim_expires_at.isoformat() if case.action_claim_expires_at else None,
        "promise_amount": float(case.promise_amount) if case.promise_amount is not None else None,
        "promise_date": case.promise_date.isoformat() if case.promise_date else None,
        "promise_status": case.promise_status,
        "write_off_at": case.write_off_at.isoformat() if case.write_off_at else None,
        "recovered_amount": float(case.recovered_amount or 0),
        "notes": case.notes,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "loan_reference": loan.loan_reference,
        "loan_status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
        "earliest_overdue_date": earliest.due_date.isoformat() if earliest else None,
        "earliest_overdue_amount": (
            float(Decimal(earliest.total_due or 0) - Decimal(earliest.paid_amount or 0)) if earliest else 0
        ),
        "last_action": _activity_payload(db, last_action) if last_action else None,
        **snapshot,
    }


@router.post("/sync")
def sync_collection_workspace(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, VIEW_ROLES)
    created = sync_overdue_collection_cases(db, company_id)
    return {
        "created": created,
        "message": f"Collections synchronised. {created} new case(s) created.",
    }


@router.get("/workspace")
def collections_workspace(
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    stage: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, VIEW_ROLES)
    query = db.query(CollectionCase).filter(CollectionCase.company_id == company_id)
    if context.branch_id:
        query = query.filter(CollectionCase.branch_id == context.branch_id)
    if status_filter:
        query = query.filter(CollectionCase.status == status_filter)
    if stage:
        query = query.filter(CollectionCase.stage == stage)
    cases = [
        _case_payload(db, row)
        for row in query.order_by(CollectionCase.days_past_due.desc(), CollectionCase.created_at.desc()).limit(1000).all()
    ]
    if search:
        token = search.strip().lower()
        cases = [
            item for item in cases
            if token in " ".join(
                str(item.get(key) or "").lower()
                for key in ("borrower_name", "loan_reference", "case_reference", "phone", "physical_address", "bank_name")
            )
        ]

    upcoming_court: list[dict[str, Any]] = []
    action_query = db.query(CollectionActivity).join(CollectionCase, CollectionCase.id == CollectionActivity.case_id).filter(
        CollectionCase.company_id == company_id,
        CollectionActivity.activity_type == "court",
    )
    if context.branch_id:
        action_query = action_query.filter(CollectionCase.branch_id == context.branch_id)
    for row in action_query.order_by(CollectionActivity.performed_at.desc()).limit(200).all():
        metadata = dict(row.metadata_json or {})
        court_date = metadata.get("court_date")
        if court_date and str(court_date) >= datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date().isoformat():
            case = db.get(CollectionCase, row.case_id)
            if case:
                payload = _case_payload(db, case)
                upcoming_court.append({
                    "activity_id": str(row.id),
                    "case_id": str(case.id),
                    "case_reference": case.case_reference,
                    "borrower_name": payload.get("borrower_name"),
                    "loan_reference": payload.get("loan_reference"),
                    "court_date": court_date,
                    "court_name": metadata.get("court_name"),
                    "court_case_number": metadata.get("court_case_number"),
                })
    upcoming_court.sort(key=lambda item: str(item.get("court_date") or ""))

    return {
        "summary": {
            "open_cases": sum(1 for item in cases if item.get("status") not in {"closed", "recovered"}),
            "legal_cases": sum(1 for item in cases if item.get("stage") == "legal" or item.get("status") == "legal"),
            "one_day_past_due": sum(1 for item in cases if int(item.get("days_past_due") or 0) == 1),
            "total_overdue": round(sum(float(item.get("overdue_amount") or 0) for item in cases), 2),
        },
        "cases": cases,
        "upcoming_court": upcoming_court[:50],
    }


@router.get("/cases/{case_id}/actions")
def list_case_actions(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    case = _case_or_404(db, context, case_id)
    rows = db.query(CollectionActivity).filter(
        CollectionActivity.case_id == case.id,
    ).order_by(CollectionActivity.performed_at.desc()).all()
    return [_activity_payload(db, row) for row in rows]


@router.post("/cases/{case_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_case_action(
    case_id: UUID,
    action_type: str = Form(...),
    custom_action_title: str | None = Form(None),
    outcome: str | None = Form(None),
    notes: str | None = Form(None),
    follow_up_at: datetime | None = Form(None),
    contact_phone: str | None = Form(None),
    visited_address: str | None = Form(None),
    court_date: date | None = Form(None),
    court_name: str | None = Form(None),
    court_case_number: str | None = Form(None),
    promise_amount: Decimal | None = Form(None),
    promise_date: date | None = Form(None),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, ACTION_ROLES)
    case = _case_or_404(db, context, case_id)
    if case.company_id != company_id:
        raise HTTPException(status_code=403, detail="Collection case is outside the active company")
    case = assert_or_claim_collection_case(db, case, context.user.id)

    action_type = action_type.strip().lower()
    allowed = {"call", "visit", "promise_to_pay", "default_notice", "court", "other"}
    if action_type not in allowed:
        raise HTTPException(status_code=422, detail=f"Action type must be one of: {', '.join(sorted(allowed))}")
    notes = (notes or "").strip()
    uploads = list(files or [])

    if action_type in {"call", "visit", "promise_to_pay", "court", "other"} and not notes:
        raise HTTPException(status_code=422, detail="A detailed action report is required")
    if action_type in {"call", "visit", "default_notice", "court", "other"} and follow_up_at is None:
        raise HTTPException(
            status_code=422,
            detail="Record the date and time for the next recovery action",
        )
    if action_type == "other" and not (custom_action_title or "").strip():
        raise HTTPException(status_code=422, detail="Give the custom recovery action a title")
    if action_type == "promise_to_pay":
        if promise_amount is None or Decimal(promise_amount) <= 0:
            raise HTTPException(status_code=422, detail="Record the amount the borrower promised to pay")
        if promise_date is None:
            raise HTTPException(status_code=422, detail="Record the promised payment date")
    if action_type == "visit" and not (visited_address or "").strip():
        raise HTTPException(status_code=422, detail="Record the address that was visited")
    if action_type == "default_notice" and not uploads:
        raise HTTPException(status_code=422, detail="Upload the written default notice or proof of service")
    if action_type == "court":
        if court_date is None:
            raise HTTPException(status_code=422, detail="Record the court/hearing date")
        if not uploads:
            raise HTTPException(status_code=422, detail="Upload court papers before recording a court action")
        default_notice = db.query(CollectionActivity.id).filter(
            CollectionActivity.case_id == case.id,
            CollectionActivity.activity_type == "default_notice",
        ).first()
        if not default_notice:
            raise HTTPException(
                status_code=409,
                detail="Record the written default notice before recording court enforcement",
            )

    metadata = {
        "custom_action_title": (custom_action_title or "").strip() or None,
        "contact_phone": (contact_phone or "").strip() or None,
        "visited_address": (visited_address or "").strip() or None,
        "court_date": court_date.isoformat() if court_date else None,
        "court_name": (court_name or "").strip() or None,
        "court_case_number": (court_case_number or "").strip() or None,
        "promise_date": promise_date.isoformat() if promise_date else None,
    }
    row = CollectionActivity(
        case_id=case.id,
        company_id=company_id,
        activity_type=action_type,
        outcome=(outcome or "").strip() or "recorded",
        notes=notes or None,
        amount=(promise_amount if action_type == "promise_to_pay" else None),
        follow_up_at=follow_up_at,
        performed_by_user_id=context.user.id,
        performed_at=datetime.now(timezone.utc),
        metadata_json=metadata,
    )
    db.add(row)
    db.flush()

    file_ids: list[str] = []
    for upload in uploads:
        stored = await save_upload(
            db,
            upload,
            context,
            category="collection_evidence",
            visibility="company",
            description=f"{action_type.replace('_', ' ').title()} evidence for {case.case_reference}",
            linked_entity_type="collection_activity",
            linked_entity_id=str(row.id),
            is_confidential=True,
            company_id=company_id,
            branch_id=case.branch_id,
        )
        file_ids.append(str(stored.id))
    metadata["document_file_ids"] = file_ids
    row.metadata_json = metadata

    case.last_contact_at = row.performed_at
    case.next_action_at = follow_up_at
    if action_type in {"call", "visit"} and case.status not in {"legal", "recovered", "closed"}:
        case.status = "contacting"
    if action_type == "promise_to_pay":
        case.status = "promise_to_pay"
        case.promise_amount = promise_amount
        case.promise_date = promise_date
        case.promise_status = "pending"
        if follow_up_at is None and promise_date is not None:
            case.next_action_at = datetime.combine(promise_date, datetime.min.time(), tzinfo=timezone.utc)
    if action_type == "default_notice":
        case.stage = "pre_legal"
        if case.status not in {"legal", "recovered", "closed"}:
            case.status = "contacting"
    if action_type == "court":
        case.stage = "legal"
        case.status = "legal"
        case.legal_handover_at = case.legal_handover_at or row.performed_at

    # Keep the Client Control Centre history aligned with collections activity.
    # The operational CollectionActivity remains the authoritative recovery log;
    # this tenant-scoped client entry is the human-readable cross-workspace view.
    account = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.company_id == company_id,
        CompanyBorrowerAccount.borrower_id == case.borrower_id,
    ).first()
    if account is not None:
        legal_action = action_type in {"default_notice", "court"}
        entry_title = {
            "call": "Collections call",
            "visit": "Collections visit",
            "promise_to_pay": "Promise to pay",
            "default_notice": "Written default notice",
            "court": "Court action",
            "other": (custom_action_title or "Collections follow-up").strip(),
        }.get(action_type, "Collections follow-up")
        entry_body = notes or (outcome or "Collection action recorded").strip()
        db.add(CompanyClientCaseEntry(
            company_id=company_id,
            branch_id=case.branch_id,
            company_borrower_account_id=account.id,
            borrower_id=case.borrower_id,
            created_by_user_id=context.user.id,
            entry_type="legal_action" if legal_action else "comment",
            category=action_type,
            title=entry_title,
            body=entry_body,
            status="open" if legal_action else "recorded",
            action_date=row.performed_at,
            reference_number=(court_case_number or case.case_reference) if legal_action else case.case_reference,
            amount=(promise_amount if action_type == "promise_to_pay" else None),
            currency="LSL",
        ))

    release_collection_case_claim(db, case, context.user.id)
    db.commit()
    db.refresh(row)
    return _activity_payload(db, row)


@router.get("/daily-reports")
def list_daily_reports(
    limit: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, VIEW_ROLES)
    query = db.query(GeneratedReport).filter(
        GeneratedReport.company_id == company_id,
        GeneratedReport.report_type == REPORT_TYPE,
    )
    if context.branch_id:
        query = query.filter(GeneratedReport.branch_id == context.branch_id)
    rows = query.order_by(GeneratedReport.period_end.desc(), GeneratedReport.generated_at.desc()).limit(limit).all()
    return [
        {
            "id": str(row.id),
            "reference": row.reference,
            "title": row.title,
            "scope_type": row.scope_type,
            "company_id": str(row.company_id) if row.company_id else None,
            "branch_id": str(row.branch_id) if row.branch_id else None,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "generated_at": row.generated_at.isoformat(),
            "metrics": dict(row.metrics or {}),
            "file": _document_payload(row.file) if row.file else None,
        }
        for row in rows
    ]


@router.post("/daily-reports/run")
def run_daily_report_now(
    report_date: date | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, ACTION_ROLES)
    target = report_date or (datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date() - timedelta(days=1))
    # The endpoint accepts the actual due date being reported. Frontend defaults to yesterday.
    reports = generate_company_reports(
        db,
        company_id=company_id,
        due_date=target,
        branch_id=context.branch_id,
    )
    return {
        "generated_or_existing": len(reports),
        "report_date": target.isoformat(),
        "message": f"Processed {len(reports)} missed-payment report scope(s) for {target.isoformat()}.",
    }
