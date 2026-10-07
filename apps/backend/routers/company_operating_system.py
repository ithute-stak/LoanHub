from __future__ import annotations

import hashlib
import secrets
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.access_control import (
    BRANCH_MANAGEMENT_ROLES,
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    COMPANY_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.company_client import CompanyBorrowerAccount
from database.models.branch import CompanyBranch
from database.models.company_operating_system import CompanyAPIKey, CompanyOperatingRecord, CompanyWebhookEndpoint
from database.models.credit_loss_provisioning import CreditLossProvisionLine, CreditLossProvisionRun
from database.models.portfolio_risk import PortfolioRiskSnapshot
from database.models.company_staff import CompanyStaff
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import InstallmentStatus, LoanStatus, PaymentStatus, TreasuryDirection, UserRole
from database.models.lending_operations import (
    CollectionCase,
    ComplianceCase,
    CreditBureauEnquiry,
    ReconciliationException,
    WorkflowInstance,
)
from database.models.origination import AffordabilityAssessment
from database.models.payment import PaymentTransaction
from database.models.repayment import RepaymentInstallment
from database.models.reporting import GeneratedReport
from database.models.system_error import SystemErrorLog
from database.models.treasury import TreasuryEntry
from database.schemas.company_operating_system import (
    APIKeyCreate,
    APIKeyIssued,
    APIKeyRead,
    CompanyAssistantRequest,
    ManagementActionCreate,
    ManagementDecisionCreate,
    ManagementResolutionCreate,
    ManagementVerificationCreate,
    PrudentialFilingReadinessCreate,
    PrudentialProfileUpsert,
    RelatedPartyRegisterCreate,
    OperatingRecordCreate,
    OperatingRecordRead,
    OperatingRecordUpdate,
    PricingSimulationRequest,
    WebhookCreate,
    WebhookIssued,
    WebhookRead,
)
from database.session import get_db
from services.interest_calculation_service import calculate_loan_terms, generate_monthly_due_dates
from services.analytics_service import build_management_command_intelligence
from services.accounting_service import accounting_audit_compliance_pack, financial_ratio_analysis, treasury_cash_forecast
from services.crypto_service import encrypt_control_secret
from services.webhook_outbox_service import WEBHOOK_SECRET_PURPOSE, validate_webhook_url

router = APIRouter(prefix="/company-operating-system", tags=["Company Operating System"])

WRITE_ROLES = (
    COMPANY_MANAGEMENT_ROLES
    | BRANCH_MANAGEMENT_ROLES
    | LENDING_ROLES
    | FINANCE_ROLES
    | COLLECTIONS_ROLES
    | {
        UserRole.CUSTOMER_SUPPORT,
        UserRole.HR_MANAGER,
        UserRole.PERFORMANCE_MANAGER,
        UserRole.RISK_MANAGER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.IT_SUPPORT,
        UserRole.AML_CFT_OFFICER,
        UserRole.DATA_PROTECTION_OFFICER,
        UserRole.REGULATORY_REPORTING_OFFICER,
        UserRole.INFORMATION_SECURITY_OFFICER,
    }
)

CAPABILITIES = [
    (1, "executive_command", "Executive Command Centre", "native analytics"),
    (2, "crm", "CRM / Customer Relationship Management", "operating records"),
    (3, "credit_committee", "Credit Committee", "workflow + operating records"),
    (4, "advanced_risk", "Advanced Credit / Risk Engine", "native analytics"),
    (5, "collateral", "Collateral, Guarantor & Security Management", "operating records"),
    (6, "treasury_liquidity", "Treasury & Liquidity Command Centre", "treasury analytics"),
    (7, "portfolio_alm", "Portfolio / Asset-Liability Management", "portfolio analytics"),
    (8, "pricing_lab", "Product & Pricing Laboratory", "loan calculation engine"),
    (9, "collections_strategy", "Collections Strategy Engine", "collection analytics"),
    (10, "legal_recovery", "Legal Recovery Centre", "operating records + collections"),
    (11, "complaints", "Complaints & Customer-Service Cases", "operating records"),
    (12, "communications", "Communication Centre", "operating records"),
    (13, "marketing", "Marketing & Customer Retention", "operating records"),
    (14, "agents", "Agent / Field Officer Management", "operating records"),
    (15, "employer_partnerships", "Employer & Payroll Partnership Management", "payroll + operating records"),
    (16, "reconciliation", "Bank / Mobile-Money Reconciliation", "native reconciliation"),
    (17, "approval_workflows", "Approval Workflow Engine", "native workflow engine"),
    (18, "procurement", "Procurement & Vendor Management", "operating records"),
    (19, "assets", "Company Asset Register", "HR assets + operating records"),
    (20, "compliance", "Regulatory & Compliance Centre", "native compliance"),
    (21, "internal_audit", "Internal Audit Centre", "operating records"),
    (22, "budgeting", "Company Budgeting & Forecasting", "operating records + analytics"),
    (23, "profitability", "Profitability Centre", "portfolio analytics"),
    (24, "targets", "Management Targets / KPIs", "operating records + performance"),
    (25, "business_continuity", "Business Continuity / Operations Health", "system health analytics"),
    (26, "integrations", "Integration Hub", "operating records"),
    (27, "api_webhooks", "API Keys & Webhooks", "secure credentials"),
    (28, "document_automation", "Document Automation", "operating records + Document Studio"),
    (29, "board_packs", "Board / Management Pack Generator", "GeneratedReport"),
    (30, "data_assistant", "Institution Data Assistant", "governed deterministic analytics"),
    (31, "govstack_interoperability", "GovStack Interoperability", "open APIs + reusable building blocks"),
    (32, "data_governance", "Privacy, Consent & Data Governance", "governance profile + audit"),
    (33, "responsible_ai", "Responsible AI Oversight", "human review + explainability controls"),
    (34, "regulatory_reporting", "CBL Regulatory Reporting", "regulatory submissions + approvals"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _is_company_management(context: TenantContext) -> bool:
    return bool(context.staff and context.staff.role in COMPANY_MANAGEMENT_ROLES)


def _branch_filter(query, model, context: TenantContext):
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES and context.branch_id:
        column = getattr(model, "branch_id", None)
        if column is not None:
            query = query.filter(or_(column == context.branch_id, column.is_(None)))
    return query


def _record_query(db: Session, context: TenantContext):
    query = db.query(CompanyOperatingRecord).filter(CompanyOperatingRecord.company_id == context.company_id)
    return _branch_filter(query, CompanyOperatingRecord, context)


def _loan_query(db: Session, context: TenantContext):
    query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == context.company_id)
    return _branch_filter(query, ClientCompanyLoan, context)


def _ensure_borrower_scope(db: Session, context: TenantContext, borrower_id: UUID) -> None:
    query = db.query(CompanyBorrowerAccount.id).filter(
        CompanyBorrowerAccount.company_id == context.company_id,
        CompanyBorrowerAccount.borrower_id == borrower_id,
    )
    query = _branch_filter(query, CompanyBorrowerAccount, context)
    if not query.first() and not _loan_query(db, context).filter(ClientCompanyLoan.borrower_id == borrower_id).first():
        raise HTTPException(status_code=404, detail="Borrower is not a client of the active company scope")


def _ensure_loan_scope(db: Session, context: TenantContext, loan_id: UUID) -> ClientCompanyLoan:
    loan = _loan_query(db, context).filter(ClientCompanyLoan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan is not available in the active company/branch scope")
    return loan


def _ensure_assignee_scope(db: Session, context: TenantContext, user_id: UUID) -> None:
    memberships = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == context.company_id,
        CompanyStaff.user_id == user_id,
        CompanyStaff.is_active.is_(True),
    ).all()
    if not memberships:
        raise HTTPException(status_code=404, detail="Assigned user is not active staff of the current company")
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES and context.branch_id:
        if not any(item.branch_id in {None, context.branch_id} for item in memberships):
            raise HTTPException(status_code=403, detail="Assigned staff member belongs to another branch")


def _validate_record_links(db: Session, context: TenantContext, payload: OperatingRecordCreate) -> None:
    loan = _ensure_loan_scope(db, context, payload.loan_id) if payload.loan_id else None
    if payload.borrower_id:
        _ensure_borrower_scope(db, context, payload.borrower_id)
    if loan and payload.borrower_id and loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="The selected loan does not belong to the selected borrower")
    if payload.assigned_user_id:
        _ensure_assignee_scope(db, context, payload.assigned_user_id)


def _portfolio_snapshot(db: Session, context: TenantContext) -> dict:
    loans = _loan_query(db, context).all()
    loan_ids = [item.id for item in loans]
    total_balance = sum((_money(item.balance) for item in loans), Decimal("0"))
    active = [item for item in loans if item.status in {LoanStatus.ACTIVE, LoanStatus.APPROVED}]
    overdue = [item for item in loans if item.is_overdue]
    contractual_margin = sum((max(_money(item.total_repayable) - _money(item.principal_amount), Decimal("0")) for item in loans), Decimal("0"))

    installments = []
    if loan_ids:
        installments = db.query(RepaymentInstallment).filter(
            RepaymentInstallment.loan_id.in_(loan_ids),
            RepaymentInstallment.is_superseded.is_(False),
        ).all()
    today = date.today()
    future_30 = today + timedelta(days=30)
    expected_30 = Decimal("0")
    overdue_due = Decimal("0")
    max_dpd_by_loan: dict[UUID, int] = defaultdict(int)
    for item in installments:
        remaining = max(_money(item.total_due) - _money(item.paid_amount), Decimal("0"))
        if remaining <= 0:
            continue
        if today <= item.due_date <= future_30:
            expected_30 += remaining
        if item.due_date < today or item.status == InstallmentStatus.OVERDUE:
            overdue_due += remaining
            max_dpd_by_loan[item.loan_id] = max(max_dpd_by_loan[item.loan_id], max((today - item.due_date).days, 1))

    def par(days: int) -> float:
        if total_balance <= 0:
            return 0.0
        exposure = sum((_money(item.balance) for item in loans if max_dpd_by_loan.get(item.id, 0) >= days), Decimal("0"))
        return round(float(exposure / total_balance * Decimal("100")), 2)

    branch_exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for item in loans:
        branch_exposure[str(item.branch_id or "unassigned")] += _money(item.balance)

    return {
        "loans_total": len(loans),
        "active_loans": len(active),
        "overdue_loans": len(overdue),
        "portfolio_balance": total_balance,
        "principal_originated": sum((_money(item.principal_amount) for item in loans), Decimal("0")),
        "contractual_margin": contractual_margin,
        "overdue_scheduled_amount": overdue_due,
        "expected_collections_30_days": expected_30,
        "par_1": par(1),
        "par_7": par(7),
        "par_30": par(30),
        "par_60": par(60),
        "par_90": par(90),
        "branch_exposure": {key: value for key, value in branch_exposure.items()},
    }


def _treasury_snapshot(db: Session, context: TenantContext) -> dict:
    query = db.query(TreasuryEntry).filter(
        TreasuryEntry.company_id == context.company_id,
        TreasuryEntry.is_voided.is_(False),
    )
    query = _branch_filter(query, TreasuryEntry, context)
    entries = query.all()
    money_in = sum((_money(item.amount) for item in entries if item.direction == TreasuryDirection.MONEY_IN), Decimal("0"))
    money_out = sum((_money(item.amount) for item in entries if item.direction == TreasuryDirection.MONEY_OUT), Decimal("0"))
    return {
        "recorded_money_in": money_in,
        "recorded_money_out": money_out,
        "net_recorded_liquidity": money_in - money_out,
        "entry_count": len(entries),
    }


def _collections_snapshot(db: Session, context: TenantContext) -> dict:
    query = db.query(CollectionCase).filter(CollectionCase.company_id == context.company_id)
    query = _branch_filter(query, CollectionCase, context)
    cases = query.all()
    buckets = {"current_or_early": 0, "1_7": 0, "8_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    exposure = {key: Decimal("0") for key in buckets}
    for item in cases:
        dpd = int(item.days_past_due or 0)
        if dpd <= 0:
            key = "current_or_early"
        elif dpd <= 7:
            key = "1_7"
        elif dpd <= 30:
            key = "8_30"
        elif dpd <= 60:
            key = "31_60"
        elif dpd <= 90:
            key = "61_90"
        else:
            key = "90_plus"
        buckets[key] += 1
        exposure[key] += _money(item.outstanding_balance)
    return {
        "open_cases": sum(1 for item in cases if item.status not in {"closed", "completed", "written_off"}),
        "case_count": len(cases),
        "buckets": buckets,
        "bucket_exposure": exposure,
        "promise_to_pay": sum(1 for item in cases if item.promise_status in {"promised", "pending"}),
        "legal_handover": sum(1 for item in cases if item.legal_handover_at is not None),
        "recovered_amount": sum((_money(item.recovered_amount) for item in cases), Decimal("0")),
    }


def _governance_snapshot(db: Session, context: TenantContext) -> dict:
    compliance_query = db.query(ComplianceCase).filter(ComplianceCase.company_id == context.company_id)
    compliance_query = _branch_filter(compliance_query, ComplianceCase, context)
    compliance = compliance_query.all()
    recon_query = db.query(ReconciliationException).filter(ReconciliationException.company_id == context.company_id)
    recon_query = _branch_filter(recon_query, ReconciliationException, context)
    recon = recon_query.all()
    workflows = db.query(WorkflowInstance).filter(WorkflowInstance.company_id == context.company_id).all()
    errors_query = db.query(SystemErrorLog).filter(
        SystemErrorLog.company_id == context.company_id,
        SystemErrorLog.is_resolved.is_(False),
    )
    errors_query = _branch_filter(errors_query, SystemErrorLog, context)
    return {
        "open_compliance_cases": sum(1 for item in compliance if item.status not in {"closed", "resolved"}),
        "high_risk_compliance_cases": sum(1 for item in compliance if item.severity in {"high", "critical"} and item.status not in {"closed", "resolved"}),
        "open_reconciliation_exceptions": sum(1 for item in recon if item.status not in {"resolved", "closed"}),
        "active_approval_workflows": sum(1 for item in workflows if item.status == "active"),
        "unresolved_system_errors": errors_query.count(),
    }


def _operating_snapshot(db: Session, context: TenantContext) -> dict:
    records = _record_query(db, context).filter(CompanyOperatingRecord.is_archived.is_(False)).all()
    by_module = Counter(item.module for item in records)
    overdue = sum(1 for item in records if item.due_at and item.due_at < _now() and item.status not in {"closed", "completed", "cancelled"})
    return {"open_records": len(records), "overdue_actions": overdue, "by_module": dict(by_module)}


def _dashboard(db: Session, context: TenantContext) -> dict:
    portfolio = _portfolio_snapshot(db, context)
    treasury = _treasury_snapshot(db, context)
    collections = _collections_snapshot(db, context)
    governance = _governance_snapshot(db, context)
    operations = _operating_snapshot(db, context)
    payments_query = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == context.company_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
    )
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES and context.branch_id:
        branch_loan_ids = [item.id for item in _loan_query(db, context).all()]
        if branch_loan_ids:
            payments_query = payments_query.filter(PaymentTransaction.loan_id.in_(branch_loan_ids))
        else:
            payments_query = payments_query.filter(PaymentTransaction.id.is_(None))
    payments = payments_query.all()
    realized_cash_flow = sum((_money(item.amount) for item in payments), Decimal("0"))
    warnings = []
    if portfolio["par_30"] >= 10:
        warnings.append({"level": "high", "title": "PAR 30 is elevated", "detail": f"{portfolio['par_30']}% of portfolio balance is at least 30 days past due."})
    if governance["open_reconciliation_exceptions"]:
        warnings.append({"level": "high", "title": "Reconciliation exceptions need attention", "detail": f"{governance['open_reconciliation_exceptions']} exception(s) remain open."})
    if governance["high_risk_compliance_cases"]:
        warnings.append({"level": "critical", "title": "High-risk compliance cases", "detail": f"{governance['high_risk_compliance_cases']} high/critical case(s) are open."})
    if operations["overdue_actions"]:
        warnings.append({"level": "medium", "title": "Overdue operating actions", "detail": f"{operations['overdue_actions']} operating action(s) are past due."})
    return {
        "generated_at": _now().isoformat(),
        "currency": "LSL",
        "portfolio": portfolio,
        "treasury": treasury,
        "collections": collections,
        "governance": governance,
        "operations": operations,
        "cash_flow": {"successful_payment_volume": realized_cash_flow, "successful_payment_count": len(payments)},
        "profitability": {
            "contractual_margin": portfolio["contractual_margin"],
            "recoveries": collections["recovered_amount"],
            "note": "Contractual margin is portfolio revenue potential, not audited accounting profit. Use Accounting for statutory profit/loss.",
        },
        "liquidity_forecast": {
            "recorded_net_liquidity": treasury["net_recorded_liquidity"],
            "expected_collections_30_days": portfolio["expected_collections_30_days"],
            "illustrative_30_day_position": treasury["net_recorded_liquidity"] + portfolio["expected_collections_30_days"],
            "note": "Forecast excludes unrecorded future expenses, funding and proposed disbursements.",
        },
        "warnings": warnings,
    }


@router.get("/capabilities")
def list_capabilities(context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    return [{"number": number, "key": key, "name": name, "implementation": implementation, "status": "active"} for number, key, name, implementation in CAPABILITIES]


@router.get("/dashboard")
def company_command_dashboard(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    return _dashboard(db, context)


@router.get("/records", response_model=list[OperatingRecordRead])
def list_operating_records(
    module: str | None = Query(default=None, max_length=60),
    status: str | None = Query(default=None, max_length=40),
    include_archived: bool = False,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = _record_query(db, context)
    if module:
        query = query.filter(CompanyOperatingRecord.module == module)
    if status:
        query = query.filter(CompanyOperatingRecord.status == status)
    if not include_archived:
        query = query.filter(CompanyOperatingRecord.is_archived.is_(False))
    return query.order_by(CompanyOperatingRecord.updated_at.desc()).limit(500).all()


@router.post("/records", response_model=OperatingRecordRead, status_code=201)
def create_operating_record(
    payload: OperatingRecordCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    _validate_record_links(db, context, payload)
    branch_id = payload.branch_id
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        branch_id = context.branch_id
    reference = f"{payload.module[:4].upper()}-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(4).upper()}"
    record = CompanyOperatingRecord(
        company_id=context.company_id,
        branch_id=branch_id,
        module=payload.module,
        record_type=payload.record_type.strip().lower(),
        reference=reference,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status.strip().lower(),
        priority=payload.priority.strip().lower(),
        borrower_id=payload.borrower_id,
        loan_id=payload.loan_id,
        assigned_user_id=payload.assigned_user_id,
        created_by_user_id=context.user.id,
        counterparty_name=payload.counterparty_name,
        amount=payload.amount,
        currency=payload.currency.upper(),
        due_at=payload.due_at,
        data=payload.data,
        tags=payload.tags,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/records/{record_id}", response_model=OperatingRecordRead)
def update_operating_record(
    record_id: UUID,
    payload: OperatingRecordUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    record = _record_query(db, context).filter(CompanyOperatingRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Operating record not found")
    changes = payload.model_dump(exclude_unset=True)
    if "assigned_user_id" in changes and changes["assigned_user_id"] is not None:
        _ensure_assignee_scope(db, context, changes["assigned_user_id"])
    for key, value in changes.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record



MANAGEMENT_ACTION_VERIFY_ROLES = COMPANY_MANAGEMENT_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}


def _management_action_query(db: Session, context: TenantContext):
    return _record_query(db, context).filter(
        CompanyOperatingRecord.module == "executive_command",
        CompanyOperatingRecord.record_type == "management_action",
        CompanyOperatingRecord.is_archived.is_(False),
    )


def _management_action_payload(record: CompanyOperatingRecord) -> dict:
    data = dict(record.data or {})
    now = _now()
    overdue = bool(
        record.due_at
        and record.due_at < now
        and record.status not in {"resolved", "verified", "cancelled"}
    )
    days_overdue = max((now.date() - record.due_at.date()).days, 0) if overdue and record.due_at else 0
    return {
        "id": str(record.id),
        "reference": record.reference,
        "branch_id": str(record.branch_id) if record.branch_id else None,
        "source_signal_id": data.get("source_signal_id"),
        "source": data.get("source"),
        "domain": data.get("domain"),
        "severity": data.get("severity"),
        "title": record.title,
        "description": record.description,
        "status": record.status,
        "priority": record.priority,
        "assigned_user_id": str(record.assigned_user_id) if record.assigned_user_id else None,
        "created_by_user_id": str(record.created_by_user_id) if record.created_by_user_id else None,
        "due_at": record.due_at.isoformat() if record.due_at else None,
        "overdue": overdue,
        "days_overdue": days_overdue,
        "escalation_level": data.get("escalation_level", 0),
        "recommended_action": data.get("recommended_action"),
        "action_url": data.get("action_url"),
        "source_signal": data.get("source_signal", {}),
        "decision": data.get("decision"),
        "decision_note": data.get("decision_note"),
        "resolution": data.get("resolution"),
        "resolved_by_user_id": data.get("resolved_by_user_id"),
        "resolved_at": data.get("resolved_at"),
        "verification_outcome": data.get("verification_outcome"),
        "verified_by_user_id": data.get("verified_by_user_id"),
        "verified_at": data.get("verified_at"),
        "timeline": data.get("timeline", []),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _append_management_timeline(
    data: dict,
    *,
    event: str,
    user_id,
    note: str | None = None,
    evidence_references: list[str] | None = None,
    extra: dict | None = None,
) -> dict:
    timeline = list(data.get("timeline") or [])
    item = {
        "event": event,
        "at": _now().isoformat(),
        "user_id": str(user_id) if user_id else None,
    }
    if note:
        item["note"] = note
    if evidence_references:
        item["evidence_references"] = evidence_references
    if extra:
        item.update(extra)
    timeline.append(item)
    return {**data, "timeline": timeline}


@router.get("/management-actions")
def list_management_actions(
    status: str | None = Query(default=None, max_length=40),
    assigned_user_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = _management_action_query(db, context)
    if status:
        query = query.filter(CompanyOperatingRecord.status == status)
    if assigned_user_id:
        query = query.filter(CompanyOperatingRecord.assigned_user_id == assigned_user_id)
    rows = query.order_by(CompanyOperatingRecord.due_at.asc(), CompanyOperatingRecord.created_at.desc()).all()
    return [_management_action_payload(row) for row in rows]


@router.post("/management-actions", status_code=201)
def create_management_action(
    payload: ManagementActionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    _ensure_assignee_scope(db, context, payload.assigned_user_id)
    branch_id = payload.branch_id
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        branch_id = context.branch_id
    elif branch_id:
        exists = db.query(CompanyBranch.id).filter(
            CompanyBranch.id == branch_id,
            CompanyBranch.company_id == context.company_id,
        ).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Branch was not found in this company")

    existing = _management_action_query(db, context).filter(
        CompanyOperatingRecord.data["source_signal_id"].astext == payload.source_signal_id,
        ~CompanyOperatingRecord.status.in_(["verified", "cancelled"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An active management action already exists for signal {payload.source_signal_id}",
        )

    now = _now()
    data = {
        "source_signal_id": payload.source_signal_id,
        "source": payload.source,
        "domain": payload.domain,
        "severity": payload.severity,
        "recommended_action": payload.recommended_action,
        "action_url": payload.action_url,
        "source_signal": {
            "id": payload.source_signal_id,
            "source": payload.source,
            "domain": payload.domain,
            "severity": payload.severity,
            "title": payload.title,
            "why_now": payload.why_now,
            "recommended_action": payload.recommended_action,
            "action_url": payload.action_url,
            "evidence": payload.evidence,
            "captured_at": now.isoformat(),
        },
        "escalation_level": 0,
        "decision": None,
        "resolution": None,
        "verification_outcome": None,
        "timeline": [{
            "event": "assigned",
            "at": now.isoformat(),
            "user_id": str(context.user.id),
            "assigned_user_id": str(payload.assigned_user_id),
            "due_at": payload.due_at.isoformat(),
        }],
    }
    reference = f"MA-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(4).upper()}"
    record = CompanyOperatingRecord(
        company_id=context.company_id,
        branch_id=branch_id,
        module="executive_command",
        record_type="management_action",
        reference=reference,
        title=payload.title.strip(),
        description=payload.why_now.strip(),
        status="assigned",
        priority=payload.severity,
        assigned_user_id=payload.assigned_user_id,
        created_by_user_id=context.user.id,
        due_at=payload.due_at,
        data=data,
        tags=["management_action", payload.domain, payload.severity, payload.source_signal_id],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _management_action_payload(record)


@router.post("/management-actions/{record_id}/decisions")
def record_management_decision(
    record_id: UUID,
    payload: ManagementDecisionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    record = _management_action_query(db, context).filter(CompanyOperatingRecord.id == record_id).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="Management action not found")
    if record.status in {"resolved", "verified", "cancelled"}:
        raise HTTPException(status_code=409, detail="Closed management actions cannot receive new decisions")
    data = dict(record.data or {})
    data["decision"] = payload.decision.strip()
    data["decision_note"] = payload.note.strip()
    data["decision_by_user_id"] = str(context.user.id)
    data["decision_at"] = _now().isoformat()
    data = _append_management_timeline(
        data,
        event="decision_recorded",
        user_id=context.user.id,
        note=payload.note.strip(),
        evidence_references=payload.evidence_references,
        extra={"decision": payload.decision.strip()},
    )
    record.data = data
    record.status = "in_progress"
    db.add(record)
    db.commit()
    db.refresh(record)
    return _management_action_payload(record)


@router.post("/management-actions/{record_id}/resolve")
def resolve_management_action(
    record_id: UUID,
    payload: ManagementResolutionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    record = _management_action_query(db, context).filter(CompanyOperatingRecord.id == record_id).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="Management action not found")
    if record.status in {"verified", "cancelled"}:
        raise HTTPException(status_code=409, detail="This management action is already closed")
    if record.assigned_user_id and record.assigned_user_id != context.user.id and not _is_company_management(context):
        raise HTTPException(status_code=403, detail="Only the assigned owner or company management can resolve this action")
    data = dict(record.data or {})
    resolved_at = _now().isoformat()
    data["resolution"] = payload.resolution.strip()
    data["resolved_by_user_id"] = str(context.user.id)
    data["resolved_at"] = resolved_at
    data["verification_outcome"] = None
    data["verified_by_user_id"] = None
    data["verified_at"] = None
    data = _append_management_timeline(
        data,
        event="resolved",
        user_id=context.user.id,
        note=payload.resolution.strip(),
        evidence_references=payload.evidence_references,
    )
    record.data = data
    record.status = "resolved"
    db.add(record)
    db.commit()
    db.refresh(record)
    return _management_action_payload(record)


@router.post("/management-actions/{record_id}/verify")
def verify_management_action(
    record_id: UUID,
    payload: ManagementVerificationCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, MANAGEMENT_ACTION_VERIFY_ROLES)
    record = _management_action_query(db, context).filter(CompanyOperatingRecord.id == record_id).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="Management action not found")
    if record.status != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved management actions can be independently verified")
    data = dict(record.data or {})
    if data.get("resolved_by_user_id") == str(context.user.id):
        raise HTTPException(status_code=409, detail="Independent verification requires a different user from the resolver")

    verified_at = _now().isoformat()
    data["verification_outcome"] = payload.outcome
    data["verified_by_user_id"] = str(context.user.id)
    data["verified_at"] = verified_at
    data = _append_management_timeline(
        data,
        event="verified" if payload.outcome == "verified" else "reopened",
        user_id=context.user.id,
        note=payload.note.strip(),
        evidence_references=payload.evidence_references,
        extra={"outcome": payload.outcome},
    )
    record.data = data
    if payload.outcome == "verified":
        record.status = "verified"
    else:
        record.status = "in_progress"
        data["resolution"] = None
        data["resolved_by_user_id"] = None
        data["resolved_at"] = None
    db.add(record)
    db.commit()
    db.refresh(record)
    return _management_action_payload(record)


@router.post("/management-actions/escalate-overdue")
def escalate_overdue_management_actions(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER})
    now = _now()
    rows = _management_action_query(db, context).filter(
        CompanyOperatingRecord.due_at.is_not(None),
        CompanyOperatingRecord.due_at < now,
        CompanyOperatingRecord.status.in_(["assigned", "in_progress", "escalated"]),
    ).with_for_update().all()
    escalated = []
    for record in rows:
        data = dict(record.data or {})
        prior_level = int(data.get("escalation_level") or 0)
        days_overdue = max((now.date() - record.due_at.date()).days, 1)
        target_level = 3 if days_overdue >= 14 else 2 if days_overdue >= 7 else 1
        if target_level <= prior_level:
            continue
        data["escalation_level"] = target_level
        data["last_escalated_at"] = now.isoformat()
        data = _append_management_timeline(
            data,
            event="overdue_escalation",
            user_id=context.user.id,
            note=f"Action is {days_overdue} day(s) overdue.",
            extra={"escalation_level": target_level, "days_overdue": days_overdue},
        )
        record.data = data
        record.status = "escalated"
        db.add(record)
        escalated.append(str(record.id))
    db.commit()
    return {
        "escalated_count": len(escalated),
        "record_ids": escalated,
        "policy_note": "Escalation changes workflow priority only; it does not execute the underlying management action.",
    }


@router.get("/risk/borrowers/{borrower_id}")
def borrower_risk_view(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    _ensure_borrower_scope(db, context, borrower_id)
    loans = _loan_query(db, context).filter(ClientCompanyLoan.borrower_id == borrower_id).all()
    overdue = sum(1 for item in loans if item.is_overdue)
    defaulted = sum(1 for item in loans if item.status == LoanStatus.DEFAULTED)
    compliance = db.query(ComplianceCase).filter(
        ComplianceCase.company_id == context.company_id,
        ComplianceCase.borrower_id == borrower_id,
        ~ComplianceCase.status.in_(["closed", "resolved"]),
    ).all()
    latest_bureau = db.query(CreditBureauEnquiry).filter(
        CreditBureauEnquiry.company_id == context.company_id,
        CreditBureauEnquiry.borrower_id == borrower_id,
    ).order_by(CreditBureauEnquiry.requested_at.desc()).first()
    latest_affordability = db.query(AffordabilityAssessment).filter(
        AffordabilityAssessment.company_id == context.company_id,
        AffordabilityAssessment.borrower_id == borrower_id,
    ).order_by(AffordabilityAssessment.created_at.desc()).first()
    score = 100
    factors = []
    if overdue:
        score -= min(35, overdue * 15)
        factors.append(f"{overdue} current overdue LoanHub loan(s)")
    if defaulted:
        score -= min(40, defaulted * 25)
        factors.append(f"{defaulted} defaulted LoanHub loan(s)")
    high_compliance = sum(1 for item in compliance if item.severity in {"high", "critical"})
    if high_compliance:
        score -= min(30, high_compliance * 15)
        factors.append(f"{high_compliance} high/critical compliance case(s)")
    if latest_bureau and latest_bureau.adverse_records:
        score -= min(30, int(latest_bureau.adverse_records) * 10)
        factors.append("Credit-bureau enquiry contains adverse records")
    if latest_affordability and _money(latest_affordability.affordability_headroom) < 0:
        score -= 20
        factors.append("Latest affordability assessment has negative headroom")
    score = max(0, min(100, score))
    band = "low" if score >= 80 else "moderate" if score >= 60 else "high" if score >= 40 else "very_high"
    return {
        "borrower_id": borrower_id,
        "internal_risk_score": score,
        "risk_band": band,
        "factors": factors or ["No material negative factor was found in the available company-scoped LoanHub records."],
        "loan_exposure": sum((_money(item.balance) for item in loans), Decimal("0")),
        "latest_affordability": None if not latest_affordability else {
            "decision": latest_affordability.decision,
            "dti_percent": latest_affordability.dti_percent,
            "affordability_headroom": latest_affordability.affordability_headroom,
        },
        "latest_bureau": None if not latest_bureau else {
            "provider": latest_bureau.provider,
            "score": latest_bureau.score,
            "risk_grade": latest_bureau.risk_grade,
            "adverse_records": latest_bureau.adverse_records,
        },
        "disclaimer": "This is LoanHub company-internal decision support, not a credit-bureau score and not an automatic lending decision.",
    }


@router.post("/pricing/simulate")
def simulate_product_pricing(
    payload: PricingSimulationRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER})
    start = date.today()
    due_dates = generate_monthly_due_dates(start, payload.term_months)
    monthly, total, details = calculate_loan_terms(
        principal=payload.principal,
        rate_percent=payload.rate_percent,
        term_months=payload.term_months,
        processing_fee=payload.processing_fee,
        interest_method=payload.interest_method,
        start_date=start,
        due_dates=due_dates,
    )
    margin = _money(total) - _money(payload.principal)
    return {
        "monthly_installment": monthly,
        "total_repayable": total,
        "contractual_margin": margin,
        "margin_percent_of_principal": round(float(margin / payload.principal * Decimal("100")), 2),
        "details": details,
        "note": "Pricing simulation is a planning tool. Published product rules, affordability and approval controls still apply.",
    }


@router.get("/collections/strategy")
def collections_strategy(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    snapshot = _collections_snapshot(db, context)
    snapshot["recommended_actions"] = {
        "1_7": "Friendly reminder and confirm payment channel.",
        "8_30": "Collector contact, promise-to-pay and affordability check.",
        "31_60": "Formal arrangement / settlement review and supervisor escalation.",
        "61_90": "Senior collections review and legal-readiness assessment.",
        "90_plus": "Legal/recovery committee review subject to company policy and applicable law.",
    }
    return snapshot


@router.get("/reconciliation/summary")
def reconciliation_summary(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    query = db.query(ReconciliationException).filter(ReconciliationException.company_id == context.company_id)
    query = _branch_filter(query, ReconciliationException, context)
    items = query.all()
    return {
        "total": len(items),
        "open": sum(1 for item in items if item.status not in {"resolved", "closed"}),
        "open_variance": sum((_money(item.variance_amount) for item in items if item.status not in {"resolved", "closed"}), Decimal("0")),
        "by_type": dict(Counter(item.exception_type for item in items if item.status not in {"resolved", "closed"})),
    }


@router.get("/api-keys", response_model=list[APIKeyRead])
def list_api_keys(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    return db.query(CompanyAPIKey).filter(CompanyAPIKey.company_id == context.company_id).order_by(CompanyAPIKey.created_at.desc()).all()


@router.post("/api-keys", response_model=APIKeyIssued, status_code=201)
def create_api_key(payload: APIKeyCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    raw = f"lhk_{secrets.token_urlsafe(32)}"
    prefix = raw[:16]
    item = CompanyAPIKey(
        company_id=context.company_id,
        name=payload.name.strip(),
        key_prefix=prefix,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        scopes=payload.scopes,
        allowed_ips=payload.allowed_ips,
        expires_at=payload.expires_at,
        created_by_user_id=context.user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIKeyIssued(**APIKeyRead.model_validate(item).model_dump(), api_key=raw)


@router.post("/api-keys/{key_id}/revoke", response_model=APIKeyRead)
def revoke_api_key(key_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    item = db.query(CompanyAPIKey).filter(CompanyAPIKey.id == key_id, CompanyAPIKey.company_id == context.company_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API key not found")
    item.revoked_at = _now()
    db.commit()
    db.refresh(item)
    return item


@router.get("/webhooks", response_model=list[WebhookRead])
def list_webhooks(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    return db.query(CompanyWebhookEndpoint).filter(CompanyWebhookEndpoint.company_id == context.company_id).order_by(CompanyWebhookEndpoint.created_at.desc()).all()


@router.post("/webhooks", response_model=WebhookIssued, status_code=201)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    raw = f"lhwh_{secrets.token_urlsafe(32)}"
    endpoint_url = validate_webhook_url(str(payload.endpoint_url))
    encrypted_secret, encryption_nonce, encryption_version = encrypt_control_secret(
        raw,
        WEBHOOK_SECRET_PURPOSE,
    )
    item = CompanyWebhookEndpoint(
        company_id=context.company_id,
        name=payload.name.strip(),
        endpoint_url=endpoint_url,
        secret_hash=hashlib.sha256(raw.encode()).hexdigest(),
        secret_prefix=raw[:16],
        encrypted_secret=encrypted_secret,
        encryption_nonce=encryption_nonce,
        encryption_version=encryption_version,
        event_types=payload.event_types,
        created_by_user_id=context.user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return WebhookIssued(**WebhookRead.model_validate(item).model_dump(), signing_secret=raw)


@router.post("/webhooks/{webhook_id}/rotate-secret", response_model=WebhookIssued)
def rotate_webhook_secret(webhook_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    item = db.query(CompanyWebhookEndpoint).filter(
        CompanyWebhookEndpoint.id == webhook_id,
        CompanyWebhookEndpoint.company_id == context.company_id,
    ).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    raw = f"lhwh_{secrets.token_urlsafe(32)}"
    encrypted_secret, encryption_nonce, encryption_version = encrypt_control_secret(raw, WEBHOOK_SECRET_PURPOSE)
    item.secret_hash = hashlib.sha256(raw.encode()).hexdigest()
    item.secret_prefix = raw[:16]
    item.encrypted_secret = encrypted_secret
    item.encryption_nonce = encryption_nonce
    item.encryption_version = encryption_version
    item.failure_count = 0
    db.commit()
    db.refresh(item)
    return WebhookIssued(**WebhookRead.model_validate(item).model_dump(), signing_secret=raw)



def _prudential_profile_record(db: Session, context: TenantContext):
    return _record_query(db, context).filter(
        CompanyOperatingRecord.module == "internal_audit",
        CompanyOperatingRecord.record_type == "prudential_profile",
        CompanyOperatingRecord.is_archived.is_(False),
    ).order_by(CompanyOperatingRecord.updated_at.desc()).first()


def _prudential_profile_payload(record: CompanyOperatingRecord | None) -> dict:
    if not record:
        return {
            "configured": False,
            "status": "not_configured",
            "jurisdiction": "Lesotho",
            "framework_name": None,
            "source_reference": None,
            "thresholds": {},
            "notes": None,
        }
    data = dict(record.data or {})
    return {
        "configured": True,
        "id": str(record.id),
        "reference": record.reference,
        "status": record.status,
        "jurisdiction": data.get("jurisdiction"),
        "framework_name": record.title,
        "effective_from": data.get("effective_from"),
        "source_reference": data.get("source_reference"),
        "thresholds": data.get("thresholds", {}),
        "notes": record.description,
        "updated_at": record.updated_at.isoformat(),
    }


def _prudential_assessment(metric: str, value, threshold, *, direction: str, unit: str = "percent") -> dict:
    if threshold is None:
        return {
            "metric": metric,
            "value": value,
            "threshold": None,
            "unit": unit,
            "status": "not_assessed",
            "reason": "No prudential threshold is configured for this metric.",
        }
    if value is None:
        return {
            "metric": metric,
            "value": None,
            "threshold": float(threshold),
            "unit": unit,
            "status": "not_assessed",
            "reason": "Required source evidence is unavailable.",
        }
    threshold_value = float(threshold)
    numeric_value = float(value)
    passed = numeric_value >= threshold_value if direction == "minimum" else numeric_value <= threshold_value
    return {
        "metric": metric,
        "value": numeric_value,
        "threshold": threshold_value,
        "unit": unit,
        "status": "pass" if passed else "breach",
        "reason": None,
    }


def _prudential_intelligence(db: Session, context: TenantContext) -> dict:
    today = date.today()
    branch_id = context.branch_id if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES else None
    profile_record = _prudential_profile_record(db, context)
    profile = _prudential_profile_payload(profile_record)
    thresholds = dict(profile.get("thresholds") or {})

    ratios = financial_ratio_analysis(
        db,
        company_id=context.company_id,
        from_date=today.replace(day=1),
        to_date=today,
        branch_id=branch_id,
    )
    treasury = treasury_cash_forecast(
        db,
        company_id=context.company_id,
        from_date=today,
        to_date=today + timedelta(days=30),
        branch_id=branch_id,
        minimum_cash=Decimal(str(thresholds.get("minimum_liquidity_buffer") or 0)),
        collection_rate=Decimal("0.85"),
        obligation_rate=Decimal("1.00"),
        unexpected_outflow=Decimal("0"),
    )

    latest_snapshot_date = db.query(func.max(PortfolioRiskSnapshot.snapshot_date)).filter(
        PortfolioRiskSnapshot.company_id == context.company_id,
    )
    if branch_id:
        latest_snapshot_date = latest_snapshot_date.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    latest_snapshot_date = latest_snapshot_date.scalar()

    exposure_total = Decimal("0.00")
    borrower_exposures: list[tuple[UUID, Decimal]] = []
    if latest_snapshot_date:
        exposure_query = db.query(
            PortfolioRiskSnapshot.borrower_id,
            func.coalesce(func.sum(PortfolioRiskSnapshot.outstanding_balance), 0),
        ).filter(
            PortfolioRiskSnapshot.company_id == context.company_id,
            PortfolioRiskSnapshot.snapshot_date == latest_snapshot_date,
            PortfolioRiskSnapshot.is_written_off.is_(False),
        )
        if branch_id:
            exposure_query = exposure_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
        rows = exposure_query.group_by(PortfolioRiskSnapshot.borrower_id).all()
        borrower_exposures = [(borrower_id, Decimal(amount or 0)) for borrower_id, amount in rows]
        exposure_total = sum((amount for _, amount in borrower_exposures), Decimal("0.00"))

    equity = Decimal(str((ratios.get("capital_structure") or {}).get("total_equity") or 0))
    capital_to_exposure = (
        float((equity / exposure_total * Decimal("100")).quantize(Decimal("0.01")))
        if exposure_total > 0 else None
    )
    max_borrower_exposure = max((amount for _, amount in borrower_exposures), default=Decimal("0.00"))
    max_borrower_exposure_pct_equity = (
        float((max_borrower_exposure / equity * Decimal("100")).quantize(Decimal("0.01")))
        if equity > 0 else None
    )

    related_records = _record_query(db, context).filter(
        CompanyOperatingRecord.module == "internal_audit",
        CompanyOperatingRecord.record_type == "related_party_register",
        CompanyOperatingRecord.status == "active",
        CompanyOperatingRecord.is_archived.is_(False),
    ).all()
    related_borrower_ids = {record.borrower_id for record in related_records if record.borrower_id}
    related_exposure = sum(
        (amount for borrower_id, amount in borrower_exposures if borrower_id in related_borrower_ids),
        Decimal("0.00"),
    )
    related_exposure_pct_equity = (
        float((related_exposure / equity * Decimal("100")).quantize(Decimal("0.01")))
        if equity > 0 else None
    )

    latest_provision = db.query(CreditLossProvisionRun).filter(
        CreditLossProvisionRun.company_id == context.company_id,
        CreditLossProvisionRun.status == "posted",
    )
    if branch_id:
        latest_provision = latest_provision.filter(CreditLossProvisionRun.branch_id == branch_id)
    latest_provision = latest_provision.order_by(
        CreditLossProvisionRun.as_of_date.desc(),
        CreditLossProvisionRun.approved_at.desc(),
    ).first()

    ecl_coverage_percent = None
    stage3_exposure = None
    if latest_provision:
        stage3_exposure_value = db.query(
            func.coalesce(func.sum(CreditLossProvisionLine.exposure), 0)
        ).filter(
            CreditLossProvisionLine.run_id == latest_provision.id,
            CreditLossProvisionLine.stage == 3,
        ).scalar()
        stage3_exposure = Decimal(stage3_exposure_value or 0)
        allowance = Decimal(latest_provision.required_allowance or 0)
        if stage3_exposure > 0:
            ecl_coverage_percent = float(
                (allowance / stage3_exposure * Decimal("100")).quantize(Decimal("0.01"))
            )

    current_ratio = (ratios.get("liquidity") or {}).get("current_ratio")
    gearing = (ratios.get("capital_structure") or {}).get("gearing_percent")
    liquidity_minimum = treasury.get("minimum_projected_cash")

    assessments = [
        _prudential_assessment(
            "capital_to_portfolio_exposure",
            capital_to_exposure,
            thresholds.get("minimum_capital_ratio_percent"),
            direction="minimum",
        ),
        _prudential_assessment(
            "current_ratio",
            current_ratio,
            thresholds.get("minimum_current_ratio"),
            direction="minimum",
            unit="ratio",
        ),
        _prudential_assessment(
            "gearing",
            gearing,
            thresholds.get("maximum_gearing_percent"),
            direction="maximum",
        ),
        _prudential_assessment(
            "single_borrower_exposure_to_equity",
            max_borrower_exposure_pct_equity,
            thresholds.get("maximum_single_borrower_exposure_percent_of_equity"),
            direction="maximum",
        ),
        _prudential_assessment(
            "related_party_exposure_to_equity",
            related_exposure_pct_equity,
            thresholds.get("maximum_related_party_exposure_percent_of_equity"),
            direction="maximum",
        ),
        _prudential_assessment(
            "ecl_coverage_of_stage3_exposure",
            ecl_coverage_percent,
            thresholds.get("minimum_ecl_coverage_percent"),
            direction="minimum",
        ),
        _prudential_assessment(
            "minimum_projected_liquidity",
            liquidity_minimum,
            thresholds.get("minimum_liquidity_buffer"),
            direction="minimum",
            unit="LSL",
        ),
    ]

    filings = _record_query(db, context).filter(
        CompanyOperatingRecord.module == "internal_audit",
        CompanyOperatingRecord.record_type == "prudential_filing",
        CompanyOperatingRecord.is_archived.is_(False),
    ).order_by(CompanyOperatingRecord.due_at.asc()).all()
    filing_payload = []
    for record in filings:
        data = dict(record.data or {})
        required = list(data.get("required_evidence") or [])
        supplied = list(data.get("evidence_references") or [])
        missing = [item for item in required if item not in supplied]
        overdue = bool(record.due_at and record.due_at < _now() and record.status != "submitted")
        filing_payload.append({
            "id": str(record.id),
            "reference": record.reference,
            "filing_name": record.title,
            "status": record.status,
            "period_end": data.get("filing_period_end"),
            "due_at": record.due_at.isoformat() if record.due_at else None,
            "required_evidence": required,
            "evidence_references": supplied,
            "missing_evidence": missing,
            "ready": not missing,
            "overdue": overdue,
        })

    breaches = [item for item in assessments if item["status"] == "breach"]
    not_assessed = [item for item in assessments if item["status"] == "not_assessed"]
    return {
        "as_of": today.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "profile": profile,
        "metrics": {
            "latest_portfolio_snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
            "portfolio_exposure": float(exposure_total),
            "total_equity": float(equity),
            "capital_to_portfolio_exposure_percent": capital_to_exposure,
            "largest_borrower_exposure": float(max_borrower_exposure),
            "largest_borrower_exposure_percent_of_equity": max_borrower_exposure_pct_equity,
            "related_party_exposure": float(related_exposure),
            "related_party_exposure_percent_of_equity": related_exposure_pct_equity,
            "related_party_count": len(related_records),
            "current_ratio": current_ratio,
            "gearing_percent": gearing,
            "minimum_projected_liquidity_30d": liquidity_minimum,
            "latest_posted_provision_reference": latest_provision.run_reference if latest_provision else None,
            "stage3_exposure": float(stage3_exposure) if stage3_exposure is not None else None,
            "required_allowance": float(latest_provision.required_allowance) if latest_provision else None,
            "ecl_coverage_percent": ecl_coverage_percent,
        },
        "assessments": assessments,
        "breach_count": len(breaches),
        "not_assessed_count": len(not_assessed),
        "filing_readiness": filing_payload,
        "related_parties": [{
            "id": str(record.id),
            "reference": record.reference,
            "borrower_id": str(record.borrower_id) if record.borrower_id else None,
            "relationship_type": (record.data or {}).get("relationship_type"),
            "relationship_description": record.description,
            "evidence_references": (record.data or {}).get("evidence_references", []),
            "branch_id": str(record.branch_id) if record.branch_id else None,
        } for record in related_records],
        "regulatory_status": (
            "breach" if breaches
            else "not_assessed" if not profile["configured"] or not_assessed
            else "within_configured_limits"
        ),
        "policy_note": (
            "Prudential assessments are performed only against explicitly configured thresholds and available LoanHub evidence. "
            "Capital-to-portfolio exposure is a management monitoring proxy, not a statutory capital adequacy ratio unless the configured framework explicitly defines it that way. "
            "Related-party status is never inferred; only borrowers explicitly entered in the related-party register are included."
        ),
    }


@router.put("/prudential/profile")
def upsert_prudential_profile(
    payload: PrudentialProfileUpsert,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(
        context,
        COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER, UserRole.REGULATORY_REPORTING_OFFICER},
    )
    record = _prudential_profile_record(db, context)
    thresholds = {
        key: float(value) if value is not None else None
        for key, value in {
            "minimum_capital_ratio_percent": payload.minimum_capital_ratio_percent,
            "minimum_current_ratio": payload.minimum_current_ratio,
            "maximum_gearing_percent": payload.maximum_gearing_percent,
            "maximum_single_borrower_exposure_percent_of_equity": payload.maximum_single_borrower_exposure_percent_of_equity,
            "maximum_related_party_exposure_percent_of_equity": payload.maximum_related_party_exposure_percent_of_equity,
            "minimum_ecl_coverage_percent": payload.minimum_ecl_coverage_percent,
            "minimum_liquidity_buffer": payload.minimum_liquidity_buffer,
        }.items()
    }
    data = {
        "jurisdiction": payload.jurisdiction,
        "effective_from": payload.effective_from.isoformat() if payload.effective_from else None,
        "source_reference": payload.source_reference,
        "thresholds": thresholds,
    }
    if record:
        record.title = payload.framework_name
        record.description = payload.notes
        record.status = "active"
        record.data = data
        record.updated_at = _now()
    else:
        record = CompanyOperatingRecord(
            company_id=context.company_id,
            branch_id=None,
            module="internal_audit",
            record_type="prudential_profile",
            reference=f"PRUD-{secrets.token_hex(4).upper()}",
            title=payload.framework_name,
            description=payload.notes,
            status="active",
            priority="high",
            created_by_user_id=context.user.id,
            data=data,
            tags=["prudential", "regulatory_profile"],
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return _prudential_profile_payload(record)


@router.post("/prudential/related-parties", status_code=201)
def create_related_party_register(
    payload: RelatedPartyRegisterCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(
        context,
        COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER, UserRole.REGULATORY_REPORTING_OFFICER},
    )
    borrower = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.company_id == context.company_id,
        CompanyBorrowerAccount.borrower_id == payload.borrower_id,
    ).first()
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower is not linked to this company")
    existing = _record_query(db, context).filter(
        CompanyOperatingRecord.module == "internal_audit",
        CompanyOperatingRecord.record_type == "related_party_register",
        CompanyOperatingRecord.borrower_id == payload.borrower_id,
        CompanyOperatingRecord.status == "active",
        CompanyOperatingRecord.is_archived.is_(False),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Borrower is already in the active related-party register")
    branch_id = payload.branch_id
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        branch_id = context.branch_id
    record = CompanyOperatingRecord(
        company_id=context.company_id,
        branch_id=branch_id,
        module="internal_audit",
        record_type="related_party_register",
        reference=f"RP-{secrets.token_hex(4).upper()}",
        title=f"Related-party borrower {payload.borrower_id}",
        description=payload.relationship_description,
        status="active",
        priority="high",
        borrower_id=payload.borrower_id,
        created_by_user_id=context.user.id,
        data={
            "relationship_type": payload.relationship_type,
            "evidence_references": payload.evidence_references,
            "classified_by_user_id": str(context.user.id),
            "classified_at": _now().isoformat(),
        },
        tags=["prudential", "related_party"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": str(record.id),
        "reference": record.reference,
        "borrower_id": str(record.borrower_id),
        "relationship_type": payload.relationship_type,
        "relationship_description": record.description,
        "evidence_references": payload.evidence_references,
    }


@router.post("/prudential/filings", status_code=201)
def create_prudential_filing(
    payload: PrudentialFilingReadinessCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(
        context,
        COMPANY_MANAGEMENT_ROLES | {UserRole.COMPLIANCE_OFFICER, UserRole.REGULATORY_REPORTING_OFFICER},
    )
    required = list(dict.fromkeys(payload.required_evidence))
    supplied = list(dict.fromkeys(payload.evidence_references))
    record = CompanyOperatingRecord(
        company_id=context.company_id,
        branch_id=None,
        module="internal_audit",
        record_type="prudential_filing",
        reference=f"REGFILE-{secrets.token_hex(4).upper()}",
        title=payload.filing_name,
        description=payload.notes,
        status="ready" if all(item in supplied for item in required) else "evidence_pending",
        priority="high",
        created_by_user_id=context.user.id,
        due_at=payload.due_at,
        data={
            "filing_period_end": payload.filing_period_end.isoformat(),
            "required_evidence": required,
            "evidence_references": supplied,
        },
        tags=["prudential", "regulatory_filing"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "reference": record.reference, "status": record.status}


@router.get("/prudential")
def get_prudential_intelligence(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    return _prudential_intelligence(db, context)


@router.post("/prudential/evidence-pack")
def generate_prudential_evidence_pack(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(
        context,
        COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES | {
            UserRole.AUDITOR,
            UserRole.RISK_MANAGER,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.REGULATORY_REPORTING_OFFICER,
        },
    )
    pack = _prudential_intelligence(db, context)
    today = date.today()
    report = GeneratedReport(
        reference=f"PRUDPACK-{today:%Y%m%d}-{secrets.token_hex(3).upper()}",
        scope_type="company",
        company_id=context.company_id,
        branch_id=context.branch_id if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES else None,
        generated_by_user_id=context.user.id,
        title=f"Prudential evidence pack - {today:%d %b %Y}",
        report_type="prudential_evidence_pack",
        output_format="json",
        period_start=today.replace(day=1),
        period_end=today,
        status="completed",
        metrics=pack,
        generated_at=_now(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": str(report.id),
        "reference": report.reference,
        "title": report.title,
        "generated_at": report.generated_at.isoformat(),
        "metrics": pack,
    }


@router.get("/board-packs")
def list_board_packs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = db.query(GeneratedReport).filter(
        GeneratedReport.company_id == context.company_id,
        GeneratedReport.report_type == "board_governance_pack",
    )
    if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES and context.branch_id:
        query = query.filter(GeneratedReport.branch_id == context.branch_id)
    rows = query.order_by(GeneratedReport.generated_at.desc()).limit(limit).all()
    return [{
        "id": str(row.id),
        "reference": row.reference,
        "title": row.title,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "status": row.status,
        "metrics": row.metrics,
    } for row in rows]


@router.post("/board-packs")
def generate_board_pack(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(
        context,
        COMPANY_MANAGEMENT_ROLES
        | FINANCE_ROLES
        | {UserRole.AUDITOR, UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER},
    )
    today = date.today()
    period_start = today.replace(day=1)
    period_end = today
    branch_id = context.branch_id if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES else None

    command = build_management_command_intelligence(
        db,
        context=context,
        date_from=period_start,
        date_to=period_end,
        branch_id=branch_id,
    )
    audit = accounting_audit_compliance_pack(
        db,
        company_id=context.company_id,
        period_start=period_start,
        period_end=period_end,
        branch_id=branch_id,
    )
    finance = financial_ratio_analysis(
        db,
        company_id=context.company_id,
        from_date=period_start,
        to_date=period_end,
        branch_id=branch_id,
    )
    treasury = treasury_cash_forecast(
        db,
        company_id=context.company_id,
        from_date=today,
        to_date=today + timedelta(days=30),
        branch_id=branch_id,
        minimum_cash=Decimal("0"),
        collection_rate=Decimal("0.85"),
        obligation_rate=Decimal("1.00"),
        unexpected_outflow=Decimal("0"),
    )

    action_rows = _management_action_query(db, context).all()
    open_actions = [
        row for row in action_rows
        if row.status not in {"verified", "cancelled"}
    ]
    verified_actions = [row for row in action_rows if row.status == "verified"]
    resolved_pending_verification = [row for row in action_rows if row.status == "resolved"]
    overdue_actions = [
        row for row in open_actions
        if row.due_at and row.due_at < _now()
    ]
    critical_open = [
        row for row in open_actions
        if str((row.data or {}).get("severity") or row.priority) == "critical"
    ]

    accountability = {
        "open_count": len(open_actions),
        "critical_open_count": len(critical_open),
        "overdue_count": len(overdue_actions),
        "resolved_pending_verification_count": len(resolved_pending_verification),
        "verified_count": len(verified_actions),
        "open_actions": [_management_action_payload(row) for row in sorted(
            open_actions,
            key=lambda item: (
                0 if str((item.data or {}).get("severity") or item.priority) == "critical"
                else 1 if str((item.data or {}).get("severity") or item.priority) == "high"
                else 2,
                item.due_at or datetime.max,
            ),
        )[:20]],
    }

    previous = db.query(GeneratedReport).filter(
        GeneratedReport.company_id == context.company_id,
        GeneratedReport.report_type == "board_governance_pack",
    )
    if branch_id:
        previous = previous.filter(GeneratedReport.branch_id == branch_id)
    previous = previous.order_by(GeneratedReport.generated_at.desc()).first()
    prior_summary = None
    if previous and previous.metrics:
        prior_metrics = dict(previous.metrics or {})
        prior_summary = {
            "reference": previous.reference,
            "generated_at": previous.generated_at.isoformat() if previous.generated_at else None,
            "enterprise_risk_score": (prior_metrics.get("command") or {}).get("enterprise_risk_score"),
            "critical_priorities": ((prior_metrics.get("command") or {}).get("priority_counts") or {}).get("critical"),
            "overdue_actions": (prior_metrics.get("accountability") or {}).get("overdue_count"),
            "audit_control_failures": (prior_metrics.get("audit") or {}).get("control_fail_count"),
            "projected_closing_cash": (prior_metrics.get("treasury") or {}).get("projected_closing_cash"),
        }

    board_attention = []
    if command["priority_counts"]["critical"]:
        board_attention.append({
            "severity": "critical",
            "title": "Critical management priorities remain open",
            "evidence": {"count": command["priority_counts"]["critical"]},
            "oversight_question": "What decisions, owners and deadlines are in place for each critical item?",
        })
    if critical_open:
        board_attention.append({
            "severity": "critical",
            "title": "Critical accountability cases remain unresolved",
            "evidence": {"count": len(critical_open), "references": [row.reference for row in critical_open[:10]]},
            "oversight_question": "Are the accountable owners and deadlines still appropriate, and what is blocking resolution?",
        })
    if overdue_actions:
        board_attention.append({
            "severity": "high",
            "title": "Management actions are overdue",
            "evidence": {"count": len(overdue_actions), "references": [row.reference for row in overdue_actions[:10]]},
            "oversight_question": "Why are these actions overdue and what escalation has occurred?",
        })
    if audit["control_fail_count"]:
        board_attention.append({
            "severity": "high",
            "title": "Finance or audit control exceptions remain open",
            "evidence": {
                "failed_control_count": audit["control_fail_count"],
                "failed_controls": [key for key, passed in audit["controls"].items() if not passed],
            },
            "oversight_question": "Which control owners are accountable for remediation before the next close?",
        })
    if treasury["minimum_projected_cash"] < 0:
        board_attention.append({
            "severity": "critical",
            "title": "30-day downside liquidity forecast falls below zero",
            "evidence": {
                "minimum_projected_cash": treasury["minimum_projected_cash"],
                "projected_closing_cash": treasury["projected_closing_cash"],
                "collection_assumption_percent": 85,
            },
            "oversight_question": "What funding, collection or commitment actions protect minimum liquidity?",
        })

    pack = {
        "governance_version": 2,
        "generated_at": _now().isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "command": command,
        "accountability": accountability,
        "finance": {
            "profitability": finance.get("profitability"),
            "liquidity": finance.get("liquidity"),
            "efficiency": finance.get("efficiency"),
            "capital_structure": finance.get("capital_structure"),
            "inputs": finance.get("inputs"),
        },
        "treasury": {
            "opening_liquidity": treasury["opening_liquidity"],
            "total_expected_collections": treasury["total_expected_collections"],
            "total_approved_obligations": treasury["total_approved_obligations"],
            "projected_closing_cash": treasury["projected_closing_cash"],
            "minimum_projected_cash": treasury["minimum_projected_cash"],
            "breach_count": treasury["breach_count"],
            "scenario": treasury["scenario"],
        },
        "audit": {
            "control_pass_count": audit["control_pass_count"],
            "control_fail_count": audit["control_fail_count"],
            "controls": audit["controls"],
            "audit_integrity": audit["audit_integrity"],
            "journal_review": {
                "journal_count": audit["journal_review"]["journal_count"],
                "flagged_count": audit["journal_review"]["flagged_count"],
                "evidence_missing_count": audit["journal_review"]["evidence_missing_count"],
            },
            "statutory_assessment": audit["statutory_assessment"],
        },
        "board_attention": board_attention,
        "opportunities": command["opportunities"],
        "prior_pack_summary": prior_summary,
        "governance_notice": (
            "This board pack is evidence-based management information generated from LoanHub records. "
            "It does not constitute an audit opinion, statutory filing, legal advice, credit approval, "
            "or authority to execute management actions without the required human approvals."
        ),
    }

    reference = f"BOARD-{today:%Y%m%d}-{secrets.token_hex(3).upper()}"
    report = GeneratedReport(
        reference=reference,
        scope_type="company",
        company_id=context.company_id,
        branch_id=branch_id,
        generated_by_user_id=context.user.id,
        title=f"Board governance pack - {today:%d %b %Y}",
        report_type="board_governance_pack",
        output_format="json",
        period_start=period_start,
        period_end=period_end,
        status="completed",
        metrics=pack,
        generated_at=_now(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": str(report.id),
        "reference": report.reference,
        "title": report.title,
        "generated_at": report.generated_at.isoformat(),
        "metrics": pack,
    }


@router.post("/assistant")
def company_data_assistant(payload: CompanyAssistantRequest, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    snapshot = _dashboard(db, context)
    question = payload.question.strip().lower()
    if any(word in question for word in ("collection", "arrears", "overdue", "par")):
        answer = (
            f"PAR 30 is {snapshot['portfolio']['par_30']}%. There are {snapshot['collections']['open_cases']} open collection cases "
            f"and {snapshot['portfolio']['overdue_loans']} overdue loans. Expected scheduled collections over 30 days are LSL {snapshot['portfolio']['expected_collections_30_days']}."
        )
        evidence = {"portfolio": snapshot["portfolio"], "collections": snapshot["collections"]}
    elif any(word in question for word in ("cash", "liquidity", "treasury", "fund")):
        answer = (
            f"Recorded net liquidity is LSL {snapshot['treasury']['net_recorded_liquidity']}. The illustrative 30-day position, adding currently scheduled collections, is "
            f"LSL {snapshot['liquidity_forecast']['illustrative_30_day_position']}."
        )
        evidence = {"treasury": snapshot["treasury"], "forecast": snapshot["liquidity_forecast"]}
    elif any(word in question for word in ("risk", "compliance", "reconciliation", "warning")):
        answer = (
            f"There are {snapshot['governance']['open_compliance_cases']} open compliance cases, "
            f"{snapshot['governance']['open_reconciliation_exceptions']} open reconciliation exceptions, and {len(snapshot['warnings'])} executive warning(s)."
        )
        evidence = {"governance": snapshot["governance"], "warnings": snapshot["warnings"]}
    elif any(word in question for word in ("profit", "margin", "income", "performance")):
        answer = (
            f"Current contractual portfolio margin is LSL {snapshot['profitability']['contractual_margin']} and recorded recoveries are LSL {snapshot['profitability']['recoveries']}. "
            "This is management decision support, not statutory profit; Accounting remains authoritative for financial statements."
        )
        evidence = {"profitability": snapshot["profitability"], "portfolio": snapshot["portfolio"]}
    else:
        answer = (
            f"The company has {snapshot['portfolio']['active_loans']} active/approved loans with LSL {snapshot['portfolio']['portfolio_balance']} outstanding, "
            f"PAR 30 of {snapshot['portfolio']['par_30']}%, and {len(snapshot['warnings'])} executive warning(s). Ask about collections, liquidity, risk/compliance, or profitability for a focused answer."
        )
        evidence = {"portfolio": snapshot["portfolio"], "warnings": snapshot["warnings"]}
    return {
        "answer": answer,
        "evidence": evidence,
        "generated_at": snapshot["generated_at"],
        "mode": "governed_deterministic_analytics",
        "notice": "The Company Data Assistant only analyses company/branch records available to the signed-in role. It does not make credit approvals, legal decisions or accounting postings.",
    }
