from io import BytesIO
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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
from database.models.enums import PaymentStatus, UserRole
from database.models.file_management import ManagedFile
from database.models.payment import PaymentTransaction
from database.models.professional_lending import PaymentReceipt
from database.models.user import User
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
from utils.payment_dates import current_payment_date, resolve_payment_date


router = APIRouter(prefix="/loans", tags=["Company Loans and Recorded Payments"])

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


@router.post("/{loan_id}/disburse", response_model=CashPaymentResult)
@router.post("/{loan_id}/cash-disburse", response_model=CashPaymentResult, include_in_schema=False)
def cash_disburse_loan(
    loan_id: UUID,
    payload: CashDisbursementCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES)
    loan = loan_or_404(db, loan_id)
    assert_tenant_loan(context, loan)
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
