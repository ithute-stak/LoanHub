from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.file_management import ManagedFile
from database.models.payment import PaymentTransaction
from database.models.professional_lending import PaymentReceipt
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from services.file_service import read_file_bytes, store_bytes
from services.document_branding_service import get_company_document_branding


MONEY = Decimal("0.01")
RECEIPT_WIDTH = 80 * mm
RECEIPT_HEIGHT = 285 * mm


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def _allocation_breakdown(db: Session, payment: PaymentTransaction) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    principal = Decimal("0")
    interest = Decimal("0")
    fees = Decimal("0")
    penalty = Decimal("0")
    rows = (
        db.query(PaymentAllocation, RepaymentInstallment)
        .join(RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id)
        .filter(PaymentAllocation.payment_id == payment.id)
        .all()
    )
    for allocation, installment in rows:
        amount = money(allocation.amount)
        total_due = money(installment.total_due)
        if total_due <= 0:
            principal += amount
            continue
        principal += money(amount * money(installment.principal_due) / total_due)
        interest += money(amount * money(installment.interest_due) / total_due)
        fees += money(amount * money(installment.fee_due) / total_due)
    allocated = money(principal + interest + fees + penalty)
    difference = money(payment.amount) - allocated
    if difference:
        principal = money(principal + difference)
    return money(principal), money(interest), money(fees), money(penalty)


def _fmt(value, currency: str = "LSL") -> str:
    symbol = "LSL" if currency.upper() == "LSL" else currency.upper()
    return f"{symbol} {money(value):,.2f}"


def _safe(value: object | None, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _payment_title(payment: PaymentTransaction) -> tuple[str, str]:
    purpose = payment.purpose.value
    if purpose == "loan_repayment":
        return "LOAN PAYMENT RECEIPT", "Amount received"
    if purpose == "loan_disbursement":
        return "LOAN DISBURSEMENT SLIP", "Amount issued"
    if purpose == "business_payment":
        return "BUSINESS PAYMENT RECEIPT", "Amount transferred"
    if purpose == "refund":
        return "REFUND RECEIPT", "Amount refunded"
    return "PAYMENT RECEIPT", "Transaction amount"


def _borrower_name(payment: PaymentTransaction) -> str:
    if payment.borrower and payment.borrower.user and payment.borrower.user.person:
        return payment.borrower.user.person.full_name
    return "Customer"


def _staff_name(payment: PaymentTransaction) -> str:
    user = payment.verified_by or payment.initiated_by
    if user and user.person:
        return user.person.full_name
    return _safe(payment.verified_by_user_id or payment.initiated_by_user_id, "System")


def _branch_name(payment: PaymentTransaction, loan: ClientCompanyLoan | None) -> str:
    branch = getattr(loan, "branch", None) if loan else None
    return _safe(getattr(branch, "name", None), "Unassigned branch")


def _image_flowable(content: bytes | None, max_width: float, max_height: float) -> Image | Paragraph:
    if not content:
        return Paragraph("", getSampleStyleSheet()["Normal"])
    try:
        from reportlab.lib.utils import ImageReader

        reader = ImageReader(BytesIO(content))
        image_width, image_height = reader.getSize()
        scale = min(max_width / float(image_width), max_height / float(image_height))
        return Image(BytesIO(content), width=image_width * scale, height=image_height * scale)
    except Exception:
        return Paragraph("", getSampleStyleSheet()["Normal"])


def _pdf_bytes(
    db: Session,
    receipt: PaymentReceipt,
    payment: PaymentTransaction,
    loan: ClientCompanyLoan | None,
) -> bytes:
    """Build a clean dual-branded 80 mm payment or disbursement slip."""
    branding = get_company_document_branding(db, payment.company)
    borrower_name = _borrower_name(payment)
    document_title, amount_label = _payment_title(payment)
    completed_at = payment.completed_at or datetime.now(timezone.utc)
    cash = payment.cash_transaction
    currency = payment.currency or "LSL"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(RECEIPT_WIDTH, RECEIPT_HEIGHT),
        rightMargin=4.5 * mm,
        leftMargin=4.5 * mm,
        topMargin=4.5 * mm,
        bottomMargin=5 * mm,
        title=f"Receipt {receipt.receipt_number}",
        author="LoanHub by Ithute Solutions",
    )
    base = getSampleStyleSheet()
    center = ParagraphStyle(
        "ReceiptCenter",
        parent=base["Normal"],
        fontSize=6.7,
        leading=8.3,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#52606D"),
    )
    company_style = ParagraphStyle(
        "ReceiptCompany",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.4,
        leading=9.6,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
    )
    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.2,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
        spaceAfter=1.0 * mm,
    )
    label_style = ParagraphStyle(
        "ReceiptLabel",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.2,
        leading=7.8,
        textColor=colors.HexColor("#374151"),
    )
    value_style = ParagraphStyle(
        "ReceiptValue",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.1,
        leading=8.8,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#111111"),
    )
    body = ParagraphStyle(
        "ReceiptBody",
        parent=base["Normal"],
        fontSize=6.8,
        leading=8.7,
        textColor=colors.HexColor("#111111"),
    )
    amount_style = ParagraphStyle(
        "ReceiptAmount",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
    )

    centre_lines: list[object] = [
        Paragraph(branding.company_name.upper(), company_style),
    ]
    if branding.identity_line:
        centre_lines.append(Paragraph(branding.identity_line, center))
    if branding.contact_line:
        centre_lines.append(Paragraph(branding.contact_line, center))
    if branding.address_line:
        centre_lines.append(Paragraph(branding.address_line, center))

    # The thermal receipt uses the same identity hierarchy as the A4 contract:
    # LoanHub system logo on the left, current company information in the
    # middle, and the company's latest stored logo on the right.
    lender_header = Table(
        [[
            _image_flowable(branding.system_logo, 15 * mm, 8 * mm),
            centre_lines,
            _image_flowable(branding.company_logo, 15 * mm, 8 * mm),
        ]],
        colWidths=[15 * mm, 39 * mm, 15 * mm],
    )
    lender_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
    ]))

    def labelled_line(label: str, value: object) -> Table:
        row = Table(
            [[Paragraph(label.upper(), label_style), Paragraph(_safe(value), value_style)]],
            colWidths=[23 * mm, 46 * mm],
        )
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ]))
        return row

    story: list[object] = [
        lender_header,
        Spacer(1, 1.2 * mm),
        Paragraph(document_title, title_style),
        Paragraph(receipt.receipt_number, center),
        Spacer(1, 0.8 * mm),
        HRFlowable(width="100%", thickness=0.55, color=colors.HexColor("#111111")),
        Spacer(1, 1.4 * mm),
    ]

    story.extend([
        labelled_line("Date", completed_at.strftime("%d %b %Y %H:%M:%S")),
        labelled_line("Customer", borrower_name),
        labelled_line("Loan", loan.loan_reference if loan else "Not linked"),
        labelled_line("Branch", _branch_name(payment, loan)),
        labelled_line("Cashier", _staff_name(payment)),
        labelled_line("Method", payment.payment_method.value.replace("_", " ").title()),
        labelled_line("Reference", payment.provider_reference or payment.id),
    ])
    if payment.proof_reference:
        story.append(labelled_line("Proof reference", payment.proof_reference))

    story.extend([
        Spacer(1, 2 * mm),
        Table(
            [[Paragraph(amount_label.upper(), label_style)], [Paragraph(_fmt(receipt.amount_received, currency), amount_style)]],
            colWidths=[69 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0F766E")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        ),
        Spacer(1, 2 * mm),
    ])

    if payment.purpose.value == "loan_repayment":
        story.extend([
            Paragraph("PAYMENT ALLOCATION", company_style),
            labelled_line("Principal", _fmt(receipt.principal_amount, currency)),
            labelled_line("Interest", _fmt(receipt.interest_amount, currency)),
            labelled_line("Fees", _fmt(receipt.fee_amount, currency)),
            labelled_line("Penalties", _fmt(receipt.penalty_amount, currency)),
            labelled_line("Balance before", _fmt(receipt.balance_before, currency)),
            labelled_line("Balance after", _fmt(receipt.balance_after, currency)),
        ])
        if cash:
            story.extend([
                labelled_line("Cash tendered", _fmt(cash.tendered_amount, currency)),
                labelled_line("Applied to loan", _fmt(cash.applied_amount, currency)),
                labelled_line("Forward payment", _fmt(cash.forward_amount, currency)),
                labelled_line("Change returned", _fmt(cash.change_amount, currency)),
                labelled_line("Instalment", cash.installment_number),
                labelled_line("Instalment remaining", _fmt(cash.installment_outstanding_after, currency)),
            ])
    elif loan:
        story.extend([
            Paragraph("DISBURSEMENT DETAILS", company_style),
            labelled_line("Principal", _fmt(loan.principal_amount, currency)),
            labelled_line("Loan balance", _fmt(receipt.balance_after, currency)),
        ])
        if loan.is_top_up:
            story.extend([
                labelled_line("Previous loan settled", _fmt(loan.top_up_settlement_amount, currency)),
                labelled_line("Cash to borrower", _fmt(loan.top_up_cash_amount, currency)),
            ])

    story.extend([
        Spacer(1, 2 * mm),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#0B63A9")),
        Spacer(1, 1.4 * mm),
        Paragraph(f"Verification code: <b>{receipt.verification_code}</b>", center),
        Paragraph("This slip was generated from the live LoanHub ledger. Keep it as proof of the individual transaction.", body),
        Spacer(1, 3 * mm),
        Paragraph("Customer signature: __________________________", body),
        Spacer(1, 2.5 * mm),
        Paragraph("Authorised signature: ________________________", body),
        Spacer(1, 3 * mm),
        Paragraph("Generated securely by LoanHub", center),
        Paragraph("Software engineering by Ithute Solutions", center),
    ])
    doc.build(story)
    return buffer.getvalue()


def generate_payment_receipt_pdf(
    db: Session,
    *,
    receipt: PaymentReceipt,
    payment: PaymentTransaction,
    loan: ClientCompanyLoan | None = None,
) -> bytes:
    """Render a receipt/slip directly from authoritative database records.

    This deliberately does not depend on ManagedFile storage. It is used by the
    print endpoint so a missing historical file can never turn an otherwise
    valid transaction receipt into HTTP 410.
    """
    resolved_loan = loan or payment.loan or (
        db.get(ClientCompanyLoan, payment.loan_id) if payment.loan_id else None
    )
    return _pdf_bytes(db, receipt, payment, resolved_loan)

def _receipt_pdf_available(db: Session, receipt: PaymentReceipt) -> bool:
    if not receipt.pdf_file_id:
        return False
    managed = db.get(ManagedFile, receipt.pdf_file_id)
    if not managed or managed.is_deleted:
        return False
    try:
        read_file_bytes(managed)
    except HTTPException as error:
        if error.status_code == 410:
            return False
        raise
    return True


def _store_receipt_pdf(
    db: Session,
    *,
    receipt: PaymentReceipt,
    payment: PaymentTransaction,
    loan: ClientCompanyLoan | None,
) -> ManagedFile:
    content = _pdf_bytes(db, receipt, payment, loan)
    owner_user_id = payment.borrower.user_id if payment.borrower else payment.initiated_by_user_id
    managed = store_bytes(
        db,
        content=content,
        original_name=f"{receipt.receipt_number}.pdf",
        mime_type="application/pdf",
        owner_user_id=owner_user_id,
        company_id=payment.company_id,
        branch_id=loan.branch_id if loan else None,
        category="payment_receipt",
        visibility="company" if payment.company_id else "private",
        description=f"Detailed payment receipt for {payment.provider_reference or payment.id}",
        linked_entity_type="payment",
        linked_entity_id=str(payment.id),
        is_confidential=True,
    )
    receipt.pdf_file_id = managed.id
    db.flush()
    return managed


def ensure_payment_receipt(
    db: Session,
    payment: PaymentTransaction,
    *,
    ensure_pdf: bool = True,
) -> PaymentReceipt | None:
    if payment.status.value != "succeeded":
        return None

    loan = payment.loan or (db.get(ClientCompanyLoan, payment.loan_id) if payment.loan_id else None)
    existing = db.query(PaymentReceipt).filter(PaymentReceipt.payment_id == payment.id).first()
    if existing:
        # Printing and listing can operate entirely from database records. Only
        # callers that explicitly need a persisted ManagedFile should trigger
        # storage repair. This keeps the print path independent of uploads.
        if ensure_pdf and not _receipt_pdf_available(db, existing):
            _store_receipt_pdf(db, receipt=existing, payment=payment, loan=loan)
        return existing

    balance_after = money(loan.balance if loan else 0)
    balance_before = money(balance_after + money(payment.amount)) if payment.purpose.value == "loan_repayment" else balance_after
    if payment.purpose.value == "loan_repayment":
        principal, interest, fees, penalty = _allocation_breakdown(db, payment)
    else:
        principal = interest = fees = penalty = Decimal("0.00")

    receipt_number = f"RCP-{datetime.now(timezone.utc):%Y%m%d}-{str(payment.id).replace('-', '')[:10].upper()}"
    verification_code = hashlib.sha256(f"{payment.id}:{payment.provider_reference}:{payment.amount}".encode("utf-8")).hexdigest()[:20].upper()
    receipt = PaymentReceipt(
        payment_id=payment.id,
        company_id=payment.company_id,
        borrower_id=payment.borrower_id,
        loan_id=payment.loan_id,
        receipt_number=receipt_number,
        balance_before=balance_before,
        amount_received=payment.amount,
        principal_amount=principal,
        interest_amount=interest,
        fee_amount=fees,
        penalty_amount=penalty,
        balance_after=balance_after,
        payment_method=payment.payment_method.value,
        provider_reference=payment.provider_reference,
        verification_code=verification_code,
    )
    db.add(receipt)
    db.flush()
    if ensure_pdf:
        _store_receipt_pdf(db, receipt=receipt, payment=payment, loan=loan)
    return receipt
