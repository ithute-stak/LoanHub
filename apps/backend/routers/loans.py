from io import BytesIO
from datetime import datetime, date, time
from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    CASHIER_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_current_active_user,
    get_tenant_context,
    require_tenant_roles,
    resolve_tenant_context,
)
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.early_settlement import LoanEarlySettlement
from database.models.enums import LoanStatus, PaymentMethod, PaymentStatus, UserRole
from database.models.audit_log import AuditLog
from database.models.file_management import ManagedFile
from database.models.payment import PaymentTransaction
from database.models.lending_operations import CDASDeductionMandate
from database.models.cdas_official import CdasOfficialMandateState
from database.models.enums import InstallmentStatus
from database.models.professional_lending import PaymentReceipt
from database.models.user import User
from database.models.person import Person
from database.schemas.cash import (
    CashDisbursementCreate,
    CashPaymentResult,
    CashRepaymentCreate,
    CashRepaymentPreviewCreate,
    InstallmentPaymentCreate,
    CashRepaymentPreviewRead,
    LoanCalculationRead,
    LoanCalculationRequest,
    MicroLoanCalculationRead,
    MicroLoanCalculationRequest,
)
from database.schemas.early_settlement import (
    EarlySettlementPayCreate,
    EarlySettlementPaymentResult,
    EarlySettlementQuoteCreate,
    EarlySettlementRead,
)
from database.schemas.loan import InstallmentDueDateAdjustmentCreate, LoanPaymentSlipRead, LoanRead
from database.config.config import settings
from database.session import get_db
from services.loan_document_service import (
    generate_loan_information_pdf,
    generate_payment_history_pdf,
    generate_repayment_schedule_pdf,
)
from services.interest_calculation_service import calculate_loan_terms, generate_monthly_due_dates
from services.early_settlement_service import (
    initiate_early_settlement_payment,
    quote_early_settlement,
)
from services.installment_service import adjust_installment_due_date
from services.loan_service import (
    calculate_micro_loan_totals,
    disburse_cash_loan,
    preview_cash_repayment,
    record_cash_repayment,
    record_installment_repayment,
)
from services.receipt_service import ensure_payment_receipt, generate_payment_receipt_pdf
from services.credit_committee_service import preview_loan_disbursement_integrity
from utils.payment_dates import current_payment_date, resolve_payment_date


router = APIRouter(prefix="/loans", tags=["Company Loans and Recorded Payments"])


class LastPaymentReversalRequest(BaseModel):
    payment_id: UUID
    reason: str = Field(min_length=12, max_length=500)


class InstallmentArrearsRolloverRequest(BaseModel):
    installment_id: UUID
    approval_reason: str = Field(min_length=12, max_length=500)
    agreement_reference: str | None = Field(default=None, max_length=180)


class FinalRolloverPostRequest(BaseModel):
    installment_id: UUID
    approved_amount: Decimal
    agreed_due_date: date
    agreement_reference: str = Field(min_length=5, max_length=180)
    approval_reference: str = Field(min_length=5, max_length=180)
    component_evidence: dict | None = None


class FinalRolloverTransferPlanRequest(BaseModel):
    installment_id: UUID
    approved_amount: Decimal
    agreed_due_date: date
    agreement_reference: str = Field(min_length=5, max_length=180)
    approval_reference: str = Field(min_length=5, max_length=180)


@router.post("/{loan_id}/installments/final-rollover-post")
def post_final_rollover_transfer(
    loan_id: UUID,
    payload: FinalRolloverPostRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Management-authorized atomic, non-cash receivable transfer."""
    # Fail closed until ledger/subledger and rollback integration tests are complete.
    raise HTTPException(status_code=503, detail="Final installment rollover posting is disabled pending accounting reconciliation and database transaction certification")
    require_tenant_roles(context, {UserRole.COMPANY_OWNER})
    loan = _tenant_loan_or_404(db, context, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    from services.final_installment_rollover_posting import post_final_rollover
    return post_final_rollover(
        db, company_id=context.company_id, parent_id=loan_id,
        installment_id=payload.installment_id, approved_amount=payload.approved_amount,
        due_date=payload.agreed_due_date,
        agreement_reference=payload.agreement_reference,
        approval_reference=payload.approval_reference,
        component_evidence=payload.component_evidence,
        actor_user_id=context.user.id, actor_role=context.role.value,
        as_of=datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date(),
    )


@router.post("/{loan_id}/installments/final-rollover-transfer-plan")
def final_rollover_transfer_plan(
    loan_id: UUID,
    payload: FinalRolloverTransferPlanRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Validate a signed rollover and show a balanced transfer, without posting."""
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})
    loan = _tenant_loan_or_404(db, context, loan_id)
    # Parent-to-child rollover must be unique: even the planning endpoint
    # rejects parents that already have a linked facility.
    existing_child = (
        db.query(ClientCompanyLoan.id)
        .filter(
            ClientCompanyLoan.company_id == context.company_id,
            ClientCompanyLoan.parent_loan_id == loan.id,
        )
        .first()
    )
    if existing_child is not None:
        raise HTTPException(
            status_code=409,
            detail="A linked child facility already exists for this loan; reconcile it before another rollover",
        )
    from services.linked_rollover_transfer_plan import prepare_linked_rollover
    from zoneinfo import ZoneInfo
    from database.config.config import settings
    return prepare_linked_rollover(
        loan, payload.installment_id,
        approved_amount=payload.approved_amount,
        effective_due_date=payload.agreed_due_date,
        agreement_reference=payload.agreement_reference,
        approval_reference=payload.approval_reference,
        as_of=datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date(),
    )


@router.get("/{loan_id}/installments/{installment_id}/final-rollover-preview")
def preview_final_balance_rollover(
    loan_id: UUID,
    installment_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Read-only proposal for a separately approved child facility."""
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})
    loan = _tenant_loan_or_404(db, context, loan_id)
    from services.final_installment_rollover_preview import preview_final_installment_rollover
    return preview_final_installment_rollover(loan, installment_id)


@router.post("/{loan_id}/installments/carry-forward")
def carry_installment_balance(
    loan_id: UUID,
    payload: InstallmentArrearsRolloverRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Management-authorised transfer of a partial-payment remainder to the next due date."""
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})
    loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.company_id == context.company_id)
        .with_for_update()
        .first()
    )
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    assert_tenant_loan(context, loan)
    from services.installment_arrears_rollover_service import carry_installment_shortfall
    return carry_installment_shortfall(
        db, loan=loan, installment_id=payload.installment_id,
        actor_user_id=context.user.id, actor_role=context.role.value,
        reason=payload.approval_reason,
        agreement_reference=payload.agreement_reference,
    )


@router.get("/{loan_id}/repayments/last")
def get_last_repayment_for_reversal(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)
    from services.loan_last_payment_reversal import latest_repayment
    return latest_repayment(db, loan)


@router.post("/{loan_id}/repayments/last/reverse")
def reverse_last_loan_payment(
    loan_id: UUID,
    payload: LastPaymentReversalRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN})
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)
    from services.loan_last_payment_reversal import reverse_latest_cash_repayment
    return reverse_latest_cash_repayment(
        db, loan_id=loan_id, company_id=context.company_id,
        payment_id=payload.payment_id, user_id=context.user.id,
        actor_role=context.role.value, reason=payload.reason,
    )

# Repayment schedule row payments may be posted by lending or cashier roles.
INSTALLMENT_PAYMENT_ROLES = CASHIER_ROLES | LENDING_ROLES


def loan_query(db: Session):
    return db.query(ClientCompanyLoan).options(
        joinedload(ClientCompanyLoan.installments),
        joinedload(ClientCompanyLoan.renewal_cycles),
        joinedload(ClientCompanyLoan.company),
        joinedload(ClientCompanyLoan.branch),
        joinedload(ClientCompanyLoan.payment_transactions),
        joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.user).joinedload(User.person),
    )


def loan_or_404(db: Session, loan_id: UUID) -> ClientCompanyLoan:
    loan = loan_query(db).filter(ClientCompanyLoan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


def loan_by_reference_or_404(db: Session, reference: str) -> ClientCompanyLoan:
    loan = (
        loan_query(db)
        .filter(ClientCompanyLoan.loan_reference == reference.strip().upper())
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan number was not found")
    return loan




def payment_receipt_payload(db: Session, payment_id: UUID) -> tuple[str | None, ManagedFile | None]:
    receipt = db.query(PaymentReceipt).filter(PaymentReceipt.payment_id == payment_id).first()
    if not receipt:
        return None, None
    managed = db.get(ManagedFile, receipt.pdf_file_id) if receipt.pdf_file_id else None
    return receipt.receipt_number, managed

def assert_tenant_loan(context: TenantContext, loan: ClientCompanyLoan) -> None:
    if loan.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    assert_branch_scope(context, loan.branch_id)






def _tenant_loan_or_404(
    db: Session,
    context: TenantContext,
    loan_id: UUID,
) -> ClientCompanyLoan:
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)
    return loan


def _pdf_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )




@router.post("/calculator", response_model=LoanCalculationRead)
def loan_calculator(payload: LoanCalculationRequest):
    # The calculator is a proposal tool, so it may auto-build monthly dates.
    # The shared calculation engine remains strict and requires explicit dates,
    # preventing persisted offers/loans from silently inventing a schedule.
    interest_start_date = payload.interest_start_date or datetime.now(
        ZoneInfo(settings.APP_TIMEZONE)
    ).date()
    due_dates = payload.due_dates or generate_monthly_due_dates(
        interest_start_date, payload.months
    )
    try:
        monthly, total, details = calculate_loan_terms(
            principal=payload.principal,
            rate_percent=payload.rate_percent,
            term_months=payload.months,
            processing_fee=payload.processing_fee,
            interest_method=payload.interest_method,
            start_date=interest_start_date,
            due_dates=due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "method": payload.interest_method,
        "method_label": details["method_label"],
        "rate_basis": details["rate_basis"],
        "principal": payload.principal,
        "rate_percent": payload.rate_percent,
        "months": payload.months,
        "processing_fee": payload.processing_fee,
        "interest_start_date": details["interest_start_date"],
        "first_payment_date": details["first_payment_date"],
        "maturity_date": details["maturity_date"],
        "total_interest": Decimal(details["total_interest"]),
        "total_repayable": total,
        "monthly_installment": monthly,
        "schedule_amounts": [Decimal(value) for value in details["schedule_amounts"]],
        "schedule": details["schedule_rows"],
        "steps": details.get("steps", []),
    }

@router.post("/calculator/micro-loan", response_model=MicroLoanCalculationRead)
def micro_loan_calculator(payload: MicroLoanCalculationRequest):
    monthly, total, details = calculate_micro_loan_totals(
        payload.principal,
        payload.rate_percent,
        payload.months,
        payload.processing_fee,
    )
    return {
        "method": "micro_loan",
        "principal": payload.principal,
        "rate_percent": payload.rate_percent,
        "months": payload.months,
        "processing_fee": payload.processing_fee,
        "total_repayable": total,
        "monthly_installment": monthly,
        "schedule_amounts": [Decimal(value) for value in details["schedule_amounts"]],
        "steps": [
            {
                "month": row["month"],
                "opening_balance": Decimal(row["opening_balance"]),
                "amount_after_rate": Decimal(row["amount_after_rate"]),
                "component_amount": Decimal(row["component_amount"]),
                "carried_balance": Decimal(row["carried_balance"]),
            }
            for row in details["steps"]
        ],
    }


@router.post("/repayments/preview", response_model=CashRepaymentPreviewRead)
@router.post("/cash-repayments/preview", response_model=CashRepaymentPreviewRead, include_in_schema=False)
def preview_repayment(
    payload: CashRepaymentPreviewCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, CASHIER_ROLES)
    loan = loan_by_reference_or_404(db, payload.loan_reference)
    assert_tenant_loan(context, loan)
    effective_payment_date = resolve_payment_date(context.role, payload.payment_date)
    return preview_cash_repayment(
        loan,
        amount_tendered=payload.amount_tendered,
        overpayment_action=payload.overpayment_action,
        installment_number=payload.installment_number,
        payment_date=effective_payment_date,
    )


@router.post("/repayments", response_model=CashPaymentResult)
@router.post("/cash-repayments", response_model=CashPaymentResult, include_in_schema=False)
def collect_cash_repayment(
    payload: CashRepaymentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, CASHIER_ROLES)
    loan = loan_by_reference_or_404(db, payload.loan_reference)
    assert_tenant_loan(context, loan)
    effective_payment_date = resolve_payment_date(context.role, payload.payment_date)
    payment, cash, preview = record_cash_repayment(
        db,
        loan=loan,
        amount_tendered=payload.amount_tendered,
        overpayment_action=payload.overpayment_action,
        installment_number=payload.installment_number,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        gateway_provider=payload.gateway_provider,
        gateway_customer_phone=payload.gateway_customer_phone,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
        payment_date=effective_payment_date,
        backdated_by_company_owner=(
            context.role == UserRole.COMPANY_OWNER
            and effective_payment_date < current_payment_date()
        ),
    )
    receipt_number, receipt_file = payment_receipt_payload(db, payment.id)
    return {
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "status": payment.status.value,
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "receipt_number": receipt_number,
        "receipt_file": receipt_file,
        "cash_transaction": cash,
        "preview": preview,
    }




@router.get("/{loan_id}/early-settlements", response_model=list[EarlySettlementRead])
def list_early_settlements(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    return (
        db.query(LoanEarlySettlement)
        .filter(
            LoanEarlySettlement.loan_id == loan.id,
            LoanEarlySettlement.company_id == context.company_id,
        )
        .order_by(LoanEarlySettlement.created_at.desc())
        .all()
    )


@router.post("/{loan_id}/early-settlements/quote", response_model=EarlySettlementRead)
def create_early_settlement_quote(
    loan_id: UUID,
    payload: EarlySettlementQuoteCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    return quote_early_settlement(
        db,
        loan=loan,
        settlement_date=payload.settlement_date,
        quoted_by_user_id=context.user.id,
        valid_for_days=payload.valid_for_days,
    )


@router.post(
    "/{loan_id}/early-settlements/{settlement_id}/pay",
    response_model=EarlySettlementPaymentResult,
)
def pay_early_settlement(
    loan_id: UUID,
    settlement_id: UUID,
    payload: EarlySettlementPayCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    quote = (
        db.query(LoanEarlySettlement)
        .filter(
            LoanEarlySettlement.id == settlement_id,
            LoanEarlySettlement.loan_id == loan.id,
            LoanEarlySettlement.company_id == context.company_id,
        )
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Early-settlement quote not found")

    payment = initiate_early_settlement_payment(
        db,
        quote=quote,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        gateway_provider=payload.gateway_provider,
        gateway_customer_phone=payload.gateway_customer_phone,
        borrower_acknowledged=payload.borrower_acknowledged,
        agreement_note=payload.agreement_note,
        agreement_reference=payload.agreement_reference,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )
    db.refresh(quote)
    receipt_number, receipt_file = payment_receipt_payload(db, payment.id)
    return {
        "settlement": quote,
        "payment": {
            "payment_id": payment.id,
            "payment_method": payment.payment_method,
            "status": payment.status.value,
            "provider_reference": payment.provider_reference,
            "proof_reference": payment.proof_reference,
            "receipt_number": receipt_number,
            "receipt_file": receipt_file,
            "cash_transaction": payment.cash_transaction,
            "preview": None,
        },
    }


class LoanRateCorrectionRequest(BaseModel):
    proposed_rate: Decimal = Field(gt=0, le=100, max_digits=6, decimal_places=3)
    expected_current_rate: Decimal = Field(ge=0, le=100)
    expected_total_repayable: Decimal = Field(gt=0)
    reason: str = Field(min_length=10, max_length=1000)
    signed_amendment_reference: str = Field(min_length=5, max_length=200)
    confirm: bool = False


def _loan_rate_correction_quote(db: Session, loan: ClientCompanyLoan, new_rate: Decimal) -> dict:
    # Repricing already-paid or provider-registered obligations is a separate
    # reversal/rescheduling workflow, never a direct update.
    if loan.status not in {LoanStatus.APPROVED, LoanStatus.ACTIVE}:
        raise HTTPException(status_code=409, detail="Only approved/active loans qualify for this correction")
    if Decimal(str(loan.amount_paid or 0)) != 0:
        raise HTTPException(status_code=409, detail="Loan has recorded repayments; use an audited restructuring workflow")
    if loan.cdas_collection_enabled:
        raise HTTPException(status_code=409, detail="Loan has CDAS collection enabled; reconcile/amend provider deduction before any repricing")
    installments = sorted(
        (item for item in loan.installments if not item.is_superseded),
        key=lambda item: item.installment_number,
    )
    if len(installments) != loan.repayment_period or any(
        Decimal(str(item.paid_amount or 0)) != 0 or item.status != InstallmentStatus.PENDING
        or item.allocations for item in installments
    ):
        raise HTTPException(status_code=409, detail="Existing installment payments, statuses or schedules prevent direct repricing")
    if db.query(CDASDeductionMandate.id).filter(CDASDeductionMandate.loan_id == loan.id).first():
        raise HTTPException(status_code=409, detail="A CDAS mandate exists: reconcile and amend the deduction externally first")
    if db.query(CdasOfficialMandateState.id).join(
        CDASDeductionMandate, CdasOfficialMandateState.mandate_id == CDASDeductionMandate.id
    ).filter(CDASDeductionMandate.loan_id == loan.id).first():
        raise HTTPException(status_code=409, detail="Official CDAS mandate exists and cannot be directly repriced")
    breakdown = loan.calculation_breakdown or {}
    recorded_start = breakdown.get("interest_start_date")
    try:
        start_date = date.fromisoformat(str(recorded_start)) if recorded_start else loan.disbursed_at.date()
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=409, detail="Original interest start date is not verifiable") from exc
    try:
        _, _, terms = calculate_loan_terms(
            principal=Decimal(str(loan.principal_amount)),
            rate_percent=new_rate,
            term_months=loan.repayment_period,
            processing_fee=Decimal(str(loan.processing_fee)),
            interest_method=loan.calculation_method,
            start_date=start_date,
            due_dates=[item.due_date for item in installments],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = terms["schedule_rows"]
    if len(rows) != len(installments):
        raise HTTPException(status_code=409, detail="New calculation does not match the existing schedule")
    return {
        "loan_id": str(loan.id), "loan_reference": loan.loan_reference,
        "old_rate": str(loan.interest_rate), "new_rate": str(new_rate),
        "old_total_repayable": str(loan.total_repayable),
        "new_total_repayable": terms["total_repayable"],
        "old_installment_amounts": [str(item.total_due) for item in installments],
        "new_installment_amounts": terms["schedule_amounts"],
        "schedule_rows": rows,
        "calculation_breakdown": terms,
    }


@router.post("/{loan_id}/interest-correction/preview")
def preview_loan_interest_correction(
    loan_id: UUID,
    proposed_rate: Decimal = Query(..., gt=0, le=100),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER})
    loan = _tenant_loan_or_404(db, context, loan_id)
    return _loan_rate_correction_quote(db, loan, proposed_rate)


@router.post("/{loan_id}/interest-correction/apply", response_model=LoanRead)
def apply_loan_interest_correction(
    loan_id: UUID,
    payload: LoanRateCorrectionRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER})
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Explicit amendment confirmation is required")
    loan = _tenant_loan_or_404(db, context, loan_id)
    db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == loan.id).with_for_update().one()
    db.refresh(loan)
    if Decimal(str(loan.interest_rate)) != payload.expected_current_rate or Decimal(str(loan.total_repayable)) != payload.expected_total_repayable:
        raise HTTPException(status_code=409, detail="Loan changed since preview; refresh the correction quote")
    quote = _loan_rate_correction_quote(db, loan, payload.proposed_rate)
    if payload.proposed_rate == payload.expected_current_rate:
        raise HTTPException(status_code=422, detail="Choose a different rate")
    old_values = {
        "interest_rate": str(loan.interest_rate),
        "total_repayable": str(loan.total_repayable),
        "balance": str(loan.balance),
        "installment_amount": str(loan.installment_amount),
        "installment_rows": [
            {"id": str(item.id), "principal_due": str(item.principal_due),
             "interest_due": str(item.interest_due), "fee_due": str(item.fee_due),
             "total_due": str(item.total_due)}
            for item in sorted(loan.installments, key=lambda i: i.installment_number)
        ],
    }
    loan.interest_rate = payload.proposed_rate
    loan.total_repayable = Decimal(quote["new_total_repayable"])
    loan.balance = loan.total_repayable
    loan.installment_amount = Decimal(quote["new_installment_amounts"][0])
    loan.calculation_breakdown = quote["calculation_breakdown"]
    for installment, schedule in zip(
        sorted((i for i in loan.installments if not i.is_superseded), key=lambda i: i.installment_number),
        quote["schedule_rows"],
    ):
        installment.principal_due = Decimal(schedule["principal_due"])
        installment.interest_due = Decimal(schedule["interest_due"])
        installment.fee_due = Decimal(schedule["fee_due"])
        installment.total_due = Decimal(schedule["total_due"])
    db.add(AuditLog(
        user_id=context.user.id, company_id=loan.company_id, branch_id=loan.branch_id,
        action="loan.interest_rate_corrected", table_name="client_company_loan",
        entity_type="loan", record_id=loan.id, severity="warning",
        description="Company-owner correction of agreed loan pricing with signed amendment",
        before_data=old_values,
        after_data={
            "interest_rate": str(loan.interest_rate),
            "total_repayable": str(loan.total_repayable),
            "balance": str(loan.balance),
            "installment_amount": str(loan.installment_amount),
            "schedule": quote["schedule_rows"],
        },
        event_data={"reason": payload.reason, "signed_amendment_reference": payload.signed_amendment_reference,
                    "interest_start_date": quote["calculation_breakdown"]["interest_start_date"]},
    ))
    db.commit()
    return _tenant_loan_or_404(db, context, loan_id)


@router.post("/{loan_id}/installments/{installment_id}/payments", response_model=CashPaymentResult)
def pay_installment(
    loan_id: UUID,
    installment_id: UUID,
    payload: InstallmentPaymentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, INSTALLMENT_PAYMENT_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    effective_payment_date = resolve_payment_date(context.role, payload.payment_date)
    payment, cash, preview = record_installment_repayment(
        db,
        loan=loan,
        installment_id=installment_id,
        amount_tendered=payload.amount_tendered,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        gateway_provider=payload.gateway_provider,
        gateway_customer_phone=payload.gateway_customer_phone,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
        payment_date=effective_payment_date,
        backdated_by_company_owner=(
            context.role == UserRole.COMPANY_OWNER
            and effective_payment_date < current_payment_date()
        ),
    )
    receipt_number, receipt_file = payment_receipt_payload(db, payment.id)
    return {
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "status": payment.status.value,
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "receipt_number": receipt_number,
        "receipt_file": receipt_file,
        "cash_transaction": cash,
        "preview": preview,
    }


@router.patch("/{loan_id}/installments/{installment_id}/due-date", response_model=LoanRead)
def adjust_due_date(
    loan_id: UUID,
    installment_id: UUID,
    payload: InstallmentDueDateAdjustmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    adjust_installment_due_date(
        db,
        loan=loan,
        installment_id=installment_id,
        new_due_date=payload.new_due_date,
        agreement_note=payload.agreement_note,
        agreement_reference=payload.agreement_reference,
        actor_user_id=context.user.id,
        actor_role=context.role,
    )
    return _tenant_loan_or_404(db, context, loan_id)


@router.get("/{loan_id}/documents/loan-information.pdf")
def loan_information_pdf(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = _tenant_loan_or_404(db, context, loan_id)
    content = generate_loan_information_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-loan-information.pdf")


@router.get("/{loan_id}/documents/repayment-schedule.pdf")
def repayment_schedule_pdf(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = _tenant_loan_or_404(db, context, loan_id)
    content = generate_repayment_schedule_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-repayment-schedule.pdf")


@router.get("/{loan_id}/documents/payment-history.pdf")
def payment_history_pdf(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = _tenant_loan_or_404(db, context, loan_id)
    content = generate_payment_history_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-payment-history.pdf")


@router.get("/{loan_id}/payment-slips", response_model=list[LoanPaymentSlipRead])
def list_payment_slips(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = _tenant_loan_or_404(db, context, loan_id)
    payments = (
        db.query(PaymentTransaction)
        .options(
            joinedload(PaymentTransaction.company),
            joinedload(PaymentTransaction.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person),
            joinedload(PaymentTransaction.loan),
            joinedload(PaymentTransaction.initiated_by).joinedload(User.person),
            joinedload(PaymentTransaction.verified_by).joinedload(User.person),
            joinedload(PaymentTransaction.cash_transaction),
        )
        .filter(
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        .order_by(PaymentTransaction.created_at.desc())
        .all()
    )

    rows: list[dict] = []
    for payment in payments:
        receipt = ensure_payment_receipt(db, payment, ensure_pdf=False)
        if not receipt:
            continue
        rows.append(
            {
                "id": receipt.id,
                "payment_id": payment.id,
                "receipt_number": receipt.receipt_number,
                "payment_purpose": payment.purpose.value,
                "payment_method": payment.payment_method.value,
                "amount": payment.amount,
                "provider_reference": payment.provider_reference,
                "verification_code": receipt.verification_code,
                "completed_at": payment.completed_at or payment.created_at,
                "pdf_file_id": receipt.pdf_file_id,
            }
        )
    db.commit()
    return rows


@router.get("/{loan_id}/payment-slips/by-payment/{payment_id}.pdf")
def payment_slip_pdf_by_payment(
    loan_id: UUID,
    payment_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Render a printable slip from the payment ledger, never from file storage.

    This route intentionally uses PaymentTransaction.id as the stable identifier.
    It cannot return HTTP 410 for a missing historical ManagedFile because no
    ManagedFile is read at all.
    """
    loan = _tenant_loan_or_404(db, context, loan_id)
    payment = (
        db.query(PaymentTransaction)
        .options(
            joinedload(PaymentTransaction.company),
            joinedload(PaymentTransaction.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person),
            joinedload(PaymentTransaction.loan),
            joinedload(PaymentTransaction.initiated_by).joinedload(User.person),
            joinedload(PaymentTransaction.verified_by).joinedload(User.person),
            joinedload(PaymentTransaction.cash_transaction),
        )
        .filter(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Successful payment was not found for this loan")

    receipt = ensure_payment_receipt(db, payment, ensure_pdf=False)
    if not receipt:
        raise HTTPException(status_code=404, detail="Payment receipt was not found")

    db.commit()
    content = generate_payment_receipt_pdf(
        db,
        receipt=receipt,
        payment=payment,
        loan=loan,
    )
    return _pdf_response(content, f"{receipt.receipt_number}.pdf")


@router.get("/{loan_id}/payment-slips/{receipt_id}.pdf")
def payment_slip_pdf(
    loan_id: UUID,
    receipt_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = _tenant_loan_or_404(db, context, loan_id)
    receipt = (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.id == receipt_id,
            PaymentReceipt.loan_id == loan.id,
        )
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Payment slip not found")

    payment = (
        db.query(PaymentTransaction)
        .options(
            joinedload(PaymentTransaction.company),
            joinedload(PaymentTransaction.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person),
            joinedload(PaymentTransaction.loan),
            joinedload(PaymentTransaction.initiated_by).joinedload(User.person),
            joinedload(PaymentTransaction.verified_by).joinedload(User.person),
            joinedload(PaymentTransaction.cash_transaction),
        )
        .filter(
            PaymentTransaction.id == receipt.payment_id,
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="The successful payment linked to this slip was not found",
        )

    # Render directly from the ledger instead of reading an old ManagedFile.
    # The payment + receipt rows are the source of truth, so printing still works
    # after a Docker redeploy, database restore, lost upload directory, or stale
    # pdf_file_id. This endpoint therefore no longer returns 410 for missing
    # generated receipt files.
    content = generate_payment_receipt_pdf(
        db,
        receipt=receipt,
        payment=payment,
        loan=loan,
    )
    return _pdf_response(content, f"{receipt.receipt_number}.pdf")


@router.get("/by-reference/{loan_reference}", response_model=LoanRead)
def get_loan_by_reference(
    loan_reference: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = loan_by_reference_or_404(db, loan_reference)
    assert_tenant_loan(context, loan)
    return loan


@router.get("/by-reference/{loan_reference}/repayment-schedule.pdf")
def print_repayment_schedule(
    loan_reference: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = loan_by_reference_or_404(db, loan_reference)
    assert_tenant_loan(context, loan)
    content = generate_repayment_schedule_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-repayment-schedule.pdf")


@router.get("/by-reference/{loan_reference}/loan-information.pdf")
def print_loan_information(
    loan_reference: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = loan_by_reference_or_404(db, loan_reference)
    assert_tenant_loan(context, loan)
    content = generate_loan_information_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-loan-information.pdf")


@router.get("/by-reference/{loan_reference}/payment-history.pdf")
def print_payment_history(
    loan_reference: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    loan = loan_by_reference_or_404(db, loan_reference)
    assert_tenant_loan(context, loan)
    content = generate_payment_history_pdf(db, loan)
    return _pdf_response(content, f"{loan.loan_reference}-payment-history.pdf")


@router.get("/", response_model=list[LoanRead])
def list_loans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = loan_query(db)
    if current_user.role == UserRole.SUPERADMIN:
        pass
    elif current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile:
            return []
        query = query.filter(ClientCompanyLoan.borrower_id == current_user.borrower_profile.id)
    else:
        context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
        query = query.filter(ClientCompanyLoan.company_id == context.company_id)

        # Company owners/admins have company-wide visibility even when their
        # staff membership is attached to a branch. Branch-scoped roles remain
        # restricted to their active branch.
        if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
            query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    return query.order_by(ClientCompanyLoan.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/reports/loan-cash-statement.pdf")
def loan_cash_statement_pdf(
    period: str = Query(..., pattern="^(weekly|monthly)$"),
    start: date = Query(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Scoped company loan cash-movement statement for a calendar week or month."""
    from datetime import timedelta, timezone
    from database.models.company import LoanCompany
    from services.loan_period_statement_service import statement_ledger, build_period_statement

    require_tenant_roles(context, CASHIER_ROLES | LENDING_ROLES | FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    zone = ZoneInfo(settings.APP_TIMEZONE)
    if period == "weekly":
        first = start - timedelta(days=start.weekday())
        last = first + timedelta(days=7)
        period_label = f"Week {first.isoformat()} to {(last - timedelta(days=1)).isoformat()}"
    else:
        first = start.replace(day=1)
        last = first.replace(year=first.year + 1, month=1) if first.month == 12 else first.replace(month=first.month + 1)
        period_label = first.strftime("%B %Y")
    begin_utc = datetime.combine(first, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = datetime.combine(last, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    branch_id = context.branch_id if context.role not in COMPANY_MANAGEMENT_ROLES else None
    postings = statement_ledger(db, company_id=context.company_id, branch_id=branch_id, start_utc=begin_utc, end_utc=end_utc)
    pdf = build_period_statement(db, company=db.get(LoanCompany, context.company_id), period=period_label,
                                 start_utc=begin_utc, end_utc=end_utc, payments=postings, timezone_name=settings.APP_TIMEZONE)
    return _pdf_response(pdf, f"loanhub-loan-cash-statement-{period}-{first.isoformat()}.pdf")


@router.get("/reports/monthly-payments.pdf")
def monthly_loan_payments_pdf(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Print actual confirmed loan repayments for a company and selected month."""
    from datetime import timezone
    from zoneinfo import ZoneInfo

    from database.models.enums import PaymentDirection, PaymentPurpose
    from services.monthly_loan_payment_report import render_monthly_loan_payments

    require_tenant_roles(context, CASHIER_ROLES | LENDING_ROLES | FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    year, month_number = map(int, month.split("-"))
    local_start = datetime(year, month_number, 1, tzinfo=ZoneInfo(settings.APP_TIMEZONE))
    if month_number == 12:
        local_end = datetime(year + 1, 1, 1, tzinfo=local_start.tzinfo)
    else:
        local_end = datetime(year, month_number + 1, 1, tzinfo=local_start.tzinfo)
    # PaymentTransaction.completed_at is a timezone-naive UTC database column.
    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    payments_query = (
        db.query(PaymentTransaction)
        .join(ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id)
        .options(joinedload(PaymentTransaction.loan))
        .filter(
            PaymentTransaction.company_id == context.company_id,
            ClientCompanyLoan.company_id == context.company_id,
            PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT,
            PaymentTransaction.direction == PaymentDirection.INBOUND,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
            PaymentTransaction.completed_at >= start_utc,
            PaymentTransaction.completed_at < end_utc,
        )
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        payments_query = payments_query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    rows = payments_query.order_by(PaymentTransaction.completed_at, PaymentTransaction.id).all()
    from database.models.company import LoanCompany
    company = db.get(LoanCompany, context.company_id)
    pdf = render_monthly_loan_payments(
        db, company=company, month=month, payments=rows,
        timezone_name=settings.APP_TIMEZONE,
    )
    return _pdf_response(pdf, f"loanhub-monthly-payments-{month}.pdf")


@router.get("/bank-submissions.zip")
def download_bank_submissions(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confidential bank collection instructions for active outstanding loans."""
    from database.models.enums import LoanStatus
    from database.models.origination import BorrowerBankAccount
    from database.models.person import Person
    from services.bank_submission_export import build_bank_submission_zip
    from services.credential_service import decrypt_credential

    context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
    require_tenant_roles(context, FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(status_code=403, detail="A lending company must be selected")
    rows = (
        db.query(ClientCompanyLoan, Person, BorrowerBankAccount)
        .join(Borrower, Borrower.id == ClientCompanyLoan.borrower_id)
        .join(Person, Person.user_id == Borrower.user_id)
        .join(
            BorrowerBankAccount,
            (BorrowerBankAccount.borrower_id == Borrower.id)
            & (BorrowerBankAccount.company_id == context.company_id),
        )
        .filter(
            ClientCompanyLoan.company_id == context.company_id,
            ClientCompanyLoan.balance > 0,
            ClientCompanyLoan.status.in_((LoanStatus.active, LoanStatus.defaulted)),
        )
        .all()
    )
    # One bank mandate per borrower; prefer salary-designated bank details.
    chosen = {}
    for loan, person, bank in rows:
        if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
            if loan.branch_id != context.branch_id:
                continue
        previous = chosen.get(loan.id)
        if previous is None or (
            bool(bank.salary_account), bool(bank.verified_at)
        ) > (
            bool(previous[2].salary_account), bool(previous[2].verified_at)
        ):
            chosen[loan.id] = (loan, person, bank)
    records = []
    for loan, person, bank in chosen.values():
        records.append({
            "name": " ".join(filter(None, (person.first_name, person.last_name))),
            "bank": bank.bank_name,
            "account": decrypt_credential(bank.account_number_encrypted),
            "branch": bank.branch_code,
            "group": loan.folio_group_code,
            "installment": loan.installment_amount,
            "balance": loan.balance,
        })
    payload, summary = build_bank_submission_zip(
        records, lender_name=context.company.name,
    )
    if not summary["rows"]:
        raise HTTPException(
            status_code=422,
            detail="No eligible loans have complete bank accounts, branch codes and work groups",
        )
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="bank-submissions.zip"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{loan_id}/processing-acknowledgement")
def acknowledge_loan_processing(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Record which authenticated staff member reviewed/processed a loan.

    This audit acknowledgement never changes loan approval or payment status.
    """
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    loan = _tenant_loan_or_404(db, context, loan_id)
    existing = (
        db.query(AuditLog)
        .filter(
            AuditLog.company_id == loan.company_id,
            AuditLog.record_id == loan.id,
            AuditLog.action == "loan.processing_acknowledged",
            AuditLog.user_id == context.user.id,
        )
        .first()
    )
    if existing is not None:
        return {"recorded": True, "already_recorded": True, "event_id": str(existing.id)}
    event = AuditLog(
        user_id=context.user.id,
        company_id=loan.company_id,
        branch_id=loan.branch_id,
        action="loan.processing_acknowledged",
        table_name="client_company_loan",
        entity_type="loan",
        record_id=loan.id,
        description="Authenticated staff member acknowledged processing this loan.",
        actor_role=getattr(context.role, "value", str(context.role)),
        status="success",
        severity="info",
        event_data={"loan_reference": loan.loan_reference},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"recorded": True, "already_recorded": False, "event_id": str(event.id)}


@router.get("/activity/company")
def get_company_loan_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    loan_reference: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Management-only loan activity. Never infer unrecorded processors."""
    if context.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Company management access required")
    if context.company_id is None:
        raise HTTPException(status_code=403, detail="Select a company")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Start date must not exceed end date")
    loans = db.query(ClientCompanyLoan.id, ClientCompanyLoan.loan_reference).filter(
        ClientCompanyLoan.company_id == context.company_id
    )
    if context.branch_id is not None:
        loans = loans.filter(ClientCompanyLoan.branch_id == context.branch_id)
    if loan_reference:
        loans = loans.filter(ClientCompanyLoan.loan_reference.ilike(f"%{loan_reference.strip()}%"))
    loan_rows = loans.all()
    by_id = {row.id: row.loan_reference for row in loan_rows}
    if not by_id:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    query = db.query(AuditLog).options(
        joinedload(AuditLog.user).joinedload(User.person)
    ).filter(
        AuditLog.company_id == context.company_id,
        AuditLog.record_id.in_(list(by_id)),
    )
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if start_date:
        query = query.filter(AuditLog.created_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(AuditLog.created_at <= datetime.combine(end_date, time.max))
    if actor:
        token = f"%{actor.strip()}%"
        # Match stored users, not snapshots or guessed actor names.
        query = query.join(User, AuditLog.user_id == User.id).outerjoin(Person, Person.user_id == User.id).filter(
            (User.email.ilike(token)) |
            (User.phone.ilike(token)) |
            (Person.first_name.ilike(token)) | (Person.last_name.ilike(token))
        )
    total = query.count()
    events = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [{
            "id": str(item.id), "loan_id": str(item.record_id),
            "loan_reference": by_id[item.record_id], "action": item.action,
            "actor_name": item.user.person.full_name if item.user and item.user.person else (
                item.user.email or item.user.phone if item.user else None
            ),
            "actor_role": item.actor_role, "occurred_at": item.created_at.isoformat(),
            "description": item.description, "status": item.status,
        } for item in events],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/{loan_id}/activity")
def get_loan_activity(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Loan-scoped, non-invented actor timeline from durable audit and workflow fields."""
    loan = _tenant_loan_or_404(db, context, loan_id)
    events = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user).joinedload(User.person))
        .filter(AuditLog.company_id == context.company_id, AuditLog.record_id == loan.id)
        .order_by(AuditLog.created_at.asc())
        .limit(500)
        .all()
    )
    items = []
    for event in events:
        if event.branch_id is not None and event.branch_id != loan.branch_id:
            continue
        actor = None
        if event.user:
            actor = event.user.person.full_name if event.user.person else (event.user.email or event.user.phone)
        items.append({
            "id": str(event.id), "action": event.action,
            "description": event.description, "actor_name": actor,
            "actor_role": event.actor_role, "occurred_at": event.created_at.isoformat() if event.created_at else None,
            "source": "audit", "status": event.status,
        })
    # First-class approval/disbursement columns provide trustworthy fallbacks.
    for action, at, user in (
        ("LOAN_APPROVED", loan.approved_at, loan.approved_by),
        ("LOAN_DISBURSED", loan.disbursed_at, loan.disbursed_by),
    ):
        if at and not any(event["action"].lower().replace("_", "") == action.lower().replace("_", "") for event in items):
            actor = user.person.full_name if user and user.person else (user.email or user.phone if user else None)
            items.append({
                "id": action.lower(), "action": action, "description": None,
                "actor_name": actor, "actor_role": None,
                "occurred_at": at.isoformat(), "source": "loan_record", "status": "recorded",
            })
    items.sort(key=lambda event: event["occurred_at"] or "")
    return {"loan_id": str(loan.id), "loan_reference": loan.loan_reference, "items": items,
            "count": len(items), "history_limit": 500}


@router.get("/{loan_id}", response_model=LoanRead)
def get_loan(
    loan_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    loan = loan_or_404(db, loan_id)
    if current_user.role == UserRole.SUPERADMIN:
        return loan
    if current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile or loan.borrower_id != current_user.borrower_profile.id:
            raise HTTPException(status_code=403, detail="Loan is not available to you")
        return loan
    context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
    assert_tenant_loan(context, loan)
    return loan


@router.get("/{loan_id}/disbursement-integrity")
def disbursement_integrity_preview(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES | LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)
    report = preview_loan_disbursement_integrity(db, loan)
    allowed_override_drift = {
        "Credit Committee clearance is missing for this loan",
        "Credit Committee pre-contract/pre-disbursement conditions remain open",
    }
    drift = set(report.get("drift") or [])
    owner_override_available = bool(
        context.role == UserRole.COMPANY_OWNER
        and not report.get("passed")
        and drift
        and drift.issubset(allowed_override_drift)
    )
    return {
        "loan_id": str(loan.id),
        "loan_reference": loan.loan_reference,
        "status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
        **report,
        "owner_override_available": owner_override_available,
        "owner_override_policy": (
            "Authenticated company owner detected. For cash payout, LoanHub will automatically bypass only "
            "Credit Committee clearance/condition blockers; all other disbursement controls remain enforced."
            if owner_override_available
            else None
        ),
        "policy_note": (
            "This preview is read-only. The same integrity controls are re-run inside the locked payout transaction; "
            "a green preview does not bypass final disbursement validation."
        ),
    }


@router.post("/{loan_id}/disburse", response_model=CashPaymentResult)
@router.post("/{loan_id}/cash-disburse", response_model=CashPaymentResult, include_in_schema=False)
def cash_disburse_loan(
    loan_id: UUID,
    payload: CashDisbursementCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES)
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)

    owner_override_verified = False
    override_reason: str | None = None

    if context.role == UserRole.COMPANY_OWNER and payload.payment_method == PaymentMethod.CASH:
        preview = preview_loan_disbursement_integrity(db, loan)
        allowed_override_drift = {
            "Credit Committee clearance is missing for this loan",
            "Credit Committee pre-contract/pre-disbursement conditions remain open",
        }
        drift = set(preview.get("drift") or [])
        if not preview.get("passed") and drift and drift.issubset(allowed_override_drift):
            owner_override_verified = True
            override_reason = "Authenticated company-owner cash disbursement: automatic Credit Committee override"
            db.add(AuditLog(
                user_id=context.user.id,
                company_id=loan.company_id,
                branch_id=loan.branch_id,
                action="loan.disbursement_owner_committee_override",
                table_name="client_company_loan",
                entity_type="loan_disbursement",
                record_id=loan.id,
                description="LoanHub automatically applied the authenticated company-owner Credit Committee override for a cash disbursement.",
                actor_role=context.role.value,
                severity="critical",
                status="success",
                changed_fields=["credit_committee_clearance"],
                event_data={
                    "loan_reference": loan.loan_reference,
                    "payment_method": payload.payment_method.value,
                    "principal_amount": str(loan.principal_amount),
                    "override_reason": override_reason,
                    "overridden_drift": sorted(drift),
                    "automatic_role_detection": True,
                },
                request_id=(request.headers.get("x-request-id") or "")[:100] or None,
                ip_address=((request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",", 1)[0].strip()[:100] or None),
                user_agent=(request.headers.get("user-agent") or "")[:500] or None,
            ))

    payment, cash = disburse_cash_loan(
        db,
        loan=loan,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
        owner_override_verified=owner_override_verified,
        owner_override_reason=override_reason,
    )
    receipt_number, receipt_file = payment_receipt_payload(db, payment.id)
    return {
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "status": payment.status.value,
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "receipt_number": receipt_number,
        "receipt_file": receipt_file,
        "cash_transaction": cash,
        "preview": None,
    }
