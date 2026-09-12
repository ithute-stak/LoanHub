from __future__ import annotations

import hashlib
import secrets
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
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
from database.models.company_operating_system import CompanyAPIKey, CompanyOperatingRecord, CompanyWebhookEndpoint
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


@router.post("/board-packs")
def generate_board_pack(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES | {UserRole.AUDITOR, UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER})
    snapshot = _dashboard(db, context)
    today = date.today()
    reference = f"BOARD-{today:%Y%m%d}-{secrets.token_hex(3).upper()}"
    report = GeneratedReport(
        reference=reference,
        scope_type="company",
        company_id=context.company_id,
        branch_id=context.branch_id if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES else None,
        generated_by_user_id=context.user.id,
        title=f"Management pack - {today:%d %b %Y}",
        report_type="board_management_pack",
        output_format="json",
        period_start=today.replace(day=1),
        period_end=today,
        status="completed",
        metrics=snapshot,
        generated_at=_now(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "reference": report.reference, "title": report.title, "generated_at": report.generated_at, "metrics": snapshot}


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
