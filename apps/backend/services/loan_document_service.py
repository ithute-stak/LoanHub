from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from types import SimpleNamespace
from xml.sax.saxutils import escape

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer
from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.professional_lending import PaymentReceipt
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from services.file_service import store_bytes
from services.pdf_design_system import (
    DocumentContext,
    build_document,
    callout,
    date_text,
    detail_card,
    document_styles,
    generated_timestamp,
    hero_block,
    humanize,
    metric_grid,
    money,
    money_text,
    progress_bar,
    safe_text,
    section,
    timeline_card,
    two_card_row,
)

MONEY = Decimal("0.01")


def _borrower_name(loan: ClientCompanyLoan) -> str:
    borrower = loan.borrower
    if borrower and borrower.user and borrower.user.person:
        return borrower.user.person.full_name
    return "Borrower"


def _borrower_person(loan: ClientCompanyLoan):
    if loan.borrower and loan.borrower.user:
        return loan.borrower.user.person
    return None


def _loan_status(loan: ClientCompanyLoan) -> str:
    return humanize(loan.status)


def _method_label(loan: ClientCompanyLoan) -> str:
    details = loan.calculation_breakdown or {}
    return safe_text(details.get("method_label"), humanize(loan.calculation_method or "micro_loan"))


def _rate_basis(loan: ClientCompanyLoan) -> str:
    details = loan.calculation_breakdown or {}
    return safe_text(details.get("rate_basis"), "Rate basis recorded by the approved loan calculation")


def _progress(loan: ClientCompanyLoan) -> float:
    total = money(loan.total_repayable)
    if total <= 0:
        return 0.0
    return float((money(loan.amount_paid) / total) * Decimal("100"))


def _schedule_rows(loan: ClientCompanyLoan) -> list[dict[str, Any]]:
    breakdown = loan.calculation_breakdown or {}
    rows = breakdown.get("schedule_rows")
    if isinstance(rows, list) and rows:
        actual_due_dates = {
            installment.installment_number: installment.due_date
            for installment in loan.installments
        }
        merged: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            number = int(item.get("installment_number") or 0)
            if number in actual_due_dates:
                item["due_date"] = actual_due_dates[number]
            merged.append(item)
        return merged

    fallback: list[dict[str, Any]] = []
    opening = money(loan.principal_amount)
    for installment in sorted(loan.installments, key=lambda item: item.installment_number):
        principal = money(installment.principal_due)
        closing = max(money(opening - principal), Decimal("0.00"))
        fallback.append({
            "installment_number": installment.installment_number,
            "period_start": None,
            "due_date": installment.due_date,
            "opening_balance": str(opening),
            "principal_due": str(principal),
            "interest_due": str(money(installment.interest_due)),
            "fee_due": str(money(installment.fee_due)),
            "total_due": str(money(installment.total_due)),
            "closing_balance": str(closing),
            "interest_segments": [],
        })
        opening = closing
    return fallback


def _installment_by_number(loan: ClientCompanyLoan) -> dict[int, RepaymentInstallment]:
    return {int(row.installment_number): row for row in loan.installments}


def _date_value(value: Any) -> str:
    if value is None:
        return "Not recorded"
    if hasattr(value, "strftime"):
        return date_text(value)
    raw = str(value)
    try:
        return datetime.fromisoformat(raw).strftime("%d %B %Y")
    except ValueError:
        return raw


def _money_from(row: dict[str, Any], key: str) -> Decimal:
    return money(row.get(key, 0))


def _daily_formula_lines(row: dict[str, Any], rate_percent: Any) -> list[str]:
    opening = _money_from(row, "opening_balance")
    rate = Decimal(str(rate_percent or 0))
    lines: list[str] = []
    segments = row.get("interest_segments") or []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        days = int(segment.get("days") or 0)
        days_in_month = int(segment.get("days_in_month") or 1)
        interest = money(segment.get("interest", 0))
        start = _date_value(segment.get("period_start"))
        end = _date_value(segment.get("period_end"))
        lines.append(
            f"{start} to {end}: {money_text(opening)} x ({rate}% / 12) x ({days}/{days_in_month}) = {money_text(interest)}"
        )
    interest_due = _money_from(row, "interest_due")
    total_due = _money_from(row, "total_due")
    fee_due = _money_from(row, "fee_due")
    principal_due = _money_from(row, "principal_due")
    closing = _money_from(row, "closing_balance")
    lines.extend([
        f"Interest for this instalment = {money_text(interest_due)}",
        f"Principal paid = {money_text(total_due)} - {money_text(interest_due)} - {money_text(fee_due)} = {money_text(principal_due)}",
        f"New principal balance = {money_text(opening)} - {money_text(principal_due)} = {money_text(closing)}",
    ])
    return lines


def _generic_formula_lines(loan: ClientCompanyLoan, row: dict[str, Any]) -> list[str]:
    method = str((loan.calculation_breakdown or {}).get("method") or loan.calculation_method or "micro_loan")
    opening = _money_from(row, "opening_balance")
    principal_due = _money_from(row, "principal_due")
    interest_due = _money_from(row, "interest_due")
    fee_due = _money_from(row, "fee_due")
    total_due = _money_from(row, "total_due")
    closing = _money_from(row, "closing_balance")

    if method == "daily_accrual_reducing":
        return _daily_formula_lines(row, loan.interest_rate)
    if method == "reducing_balance":
        monthly_rate = Decimal(str(loan.interest_rate or 0)) / Decimal("12")
        return [
            f"Monthly rate = {Decimal(str(loan.interest_rate or 0))}% / 12 = {monthly_rate:.6f}%",
            f"Interest = {money_text(opening)} x {monthly_rate:.6f}% = {money_text(interest_due)}",
            f"Principal = {money_text(total_due)} - {money_text(interest_due)} - {money_text(fee_due)} = {money_text(principal_due)}",
            f"Closing principal = {money_text(opening)} - {money_text(principal_due)} = {money_text(closing)}",
        ]
    if method == "compound_interest":
        return [
            f"Interest is calculated on the capitalised balance for the cycle: {money_text(interest_due)}",
            f"Scheduled payment = principal {money_text(principal_due)} + interest {money_text(interest_due)} + fees {money_text(fee_due)} = {money_text(total_due)}",
            f"Principal carried to the next period after the scheduled principal reduction = {money_text(closing)}",
        ]
    if method in {"simple_interest", "flat_rate"}:
        return [
            f"Interest is allocated from the total interest calculated on the original principal: {money_text(interest_due)}",
            f"Scheduled payment = principal {money_text(principal_due)} + interest {money_text(interest_due)} + fees {money_text(fee_due)} = {money_text(total_due)}",
            f"Remaining scheduled principal = {money_text(closing)}",
        ]

    breakdown = loan.calculation_breakdown or {}
    steps = breakdown.get("steps") or []
    number = int(row.get("installment_number") or 0)
    cycle = next((item for item in steps if int(item.get("month") or 0) == number), None)
    if cycle:
        return [
            f"Opening cycle balance = {money_text(cycle.get('opening_balance', 0))}",
            f"Balance after applying the product rate = {money_text(cycle.get('amount_after_rate', 0))}",
            f"Cycle contribution = {money_text(cycle.get('component_amount', 0))}",
            f"Balance carried into the next cycle = {money_text(cycle.get('carried_balance', 0))}",
        ]
    return [
        f"Scheduled payment = principal {money_text(principal_due)} + interest {money_text(interest_due)} + fees {money_text(fee_due)} = {money_text(total_due)}",
        f"Remaining scheduled principal after this instalment = {money_text(closing)}",
    ]


def _schedule_card(loan: ClientCompanyLoan, row: dict[str, Any], actual: RepaymentInstallment | None, *, include_formula: bool = True):
    number = int(row.get("installment_number") or 0)
    due_date = actual.due_date if actual else row.get("due_date")
    status = humanize(actual.status if actual else "scheduled")
    paid = money(actual.paid_amount if actual else 0)
    total = _money_from(row, "total_due")
    remaining = max(total - paid, Decimal("0.00"))
    tone = "green" if status.lower() == "paid" else "amber" if "partial" in status.lower() or "overdue" in status.lower() else "blue"
    body = (
        f"The instalment due on <b>{escape(_date_value(due_date))}</b> starts with an outstanding principal of "
        f"<b>{money_text(_money_from(row, 'opening_balance'))}</b>. It allocates "
        f"<b>{money_text(_money_from(row, 'principal_due'))}</b> to principal, "
        f"<b>{money_text(_money_from(row, 'interest_due'))}</b> to interest and "
        f"<b>{money_text(_money_from(row, 'fee_due'))}</b> to fees. The scheduled amount is "
        f"<b>{money_text(total)}</b>. Payments recorded against this instalment total "
        f"<b>{money_text(paid)}</b>, leaving <b>{money_text(remaining)}</b> for this instalment."
    )
    meta = (
        f"Opening principal {money_text(_money_from(row, 'opening_balance'))} | "
        f"Closing principal {money_text(_money_from(row, 'closing_balance'))}"
    )
    return timeline_card(
        str(number),
        f"Instalment {number}",
        body,
        meta=meta,
        status=status,
        tone=tone,
        formula_lines=_generic_formula_lines(loan, row) if include_formula else None,
    )


def _document_context(db: Session, loan: ClientCompanyLoan, title: str) -> DocumentContext:
    return DocumentContext(
        db=db,
        company=loan.company,
        title=title,
        reference=loan.loan_reference,
        footer_note=generated_timestamp(),
        confidential=True,
    )


def _borrower_cards(loan: ClientCompanyLoan):
    person = _borrower_person(loan)
    user = loan.borrower.user if loan.borrower else None
    address = ", ".join(
        str(value).strip()
        for value in [
            getattr(person, "physical_address", None),
            getattr(person, "town_or_village", None),
            getattr(person, "district", None),
        ]
        if value and str(value).strip()
    )
    identity = getattr(person, "national_id", None) or getattr(person, "passport_number", None)
    left = detail_card(
        "Borrower profile",
        [
            ("Full name", _borrower_name(loan)),
            ("Identity", safe_text(identity)),
            ("Phone", safe_text(getattr(user, "phone", None))),
            ("Email", safe_text(getattr(user, "email", None))),
            ("Address", safe_text(address)),
        ],
        tone="blue",
    )
    right = detail_card(
        "Facility terms",
        [
            ("Method", _method_label(loan)),
            ("Interest rate", f"{Decimal(str(loan.interest_rate or 0)):,.3f}%"),
            ("Rate basis", _rate_basis(loan)),
            ("Term", f"{loan.repayment_period} month(s)"),
            ("First due date", date_text(loan.first_payment_due)),
            ("Maturity date", date_text(loan.maturity_date)),
        ],
        tone="teal",
    )
    return two_card_row(left, right)


def generate_loan_information_pdf(db: Session, loan: ClientCompanyLoan) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    story.extend(hero_block(
        "Loan Information Statement",
        "A complete account summary showing the approved facility, calculation method, repayment progress and current balance.",
        loan.loan_reference,
        status=_loan_status(loan),
        styles=styles,
    ))
    story.append(metric_grid([
        ("Principal approved", money_text(loan.principal_amount), "Capital advanced to the borrower", "blue"),
        ("Total repayable", money_text(loan.total_repayable), "Principal, interest and approved fees", "slate"),
        ("Amount paid", money_text(loan.amount_paid), f"{_progress(loan):,.1f}% of the agreement value", "green"),
        ("Outstanding", money_text(loan.balance), "Current ledger balance", "amber" if money(loan.balance) > 0 else "green"),
    ], columns=2, styles=styles))
    story.extend(section("Borrower and facility details", "The information below is taken from the active borrower and loan records.", styles=styles))
    story.append(_borrower_cards(loan))
    story.append(Spacer(1, 4 * mm))
    story.append(progress_bar("Repayment progress", _progress(loan), note=f"Paid {money_text(loan.amount_paid)}", tone="green" if _progress(loan) >= 100 else "blue", styles=styles))

    story.extend(section("How the loan was calculated", "The same calculation data drives the agreement, schedule, statements and payment allocation.", styles=styles))
    story.append(callout(
        _method_label(loan),
        f"{_rate_basis(loan)}. The approved annual or cycle rate is {Decimal(str(loan.interest_rate or 0)):,.3f}%. The processing fee is {money_text(loan.processing_fee)}.",
        tone="teal",
        styles=styles,
    ))
    story.append(Spacer(1, 3 * mm))
    rows = _schedule_rows(loan)
    actuals = _installment_by_number(loan)
    for row in rows:
        number = int(row.get("installment_number") or 0)
        story.append(_schedule_card(loan, row, actuals.get(number), include_formula=True))
        story.append(Spacer(1, 2.5 * mm))

    story.extend(section("Account interpretation", styles=styles))
    overdue = any("overdue" in humanize(item.status).lower() for item in loan.installments)
    if money(loan.balance) <= 0:
        story.append(callout("Account settled", "The ledger balance is zero. Confirm that the final receipt and settlement confirmation have been issued to the borrower.", tone="green", styles=styles))
    elif overdue:
        story.append(callout("Attention required", "At least one instalment is overdue. Review the latest payment allocation, contact the borrower through the approved process and preserve all notices in the account record.", tone="red", styles=styles))
    else:
        story.append(callout("Account in progress", f"The borrower has paid {money_text(loan.amount_paid)} and the remaining ledger balance is {money_text(loan.balance)}. Continue issuing an individual payment slip for every transaction.", tone="blue", styles=styles))

    return build_document(
        story=story,
        context=_document_context(db, loan, "Loan Information Statement"),
        title=f"Loan Information {loan.loan_reference}",
        author=f"{safe_text(getattr(loan.company, 'name', None), 'Loan company')} via LoanHub",
        subject="Detailed loan information statement",
    )


def generate_repayment_schedule_pdf(db: Session, loan: ClientCompanyLoan) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    story.extend(hero_block(
        "Repayment Schedule",
        "A step-by-step schedule explaining the principal, interest, fees, payment status and balance movement for every instalment.",
        loan.loan_reference,
        status=_loan_status(loan),
        styles=styles,
    ))
    rows = _schedule_rows(loan)
    total_interest = sum((_money_from(row, "interest_due") for row in rows), Decimal("0"))
    total_fees = sum((_money_from(row, "fee_due") for row in rows), Decimal("0"))
    story.append(metric_grid([
        ("Principal", money_text(loan.principal_amount), "Original capital", "blue"),
        ("Interest", money_text(total_interest), _method_label(loan), "teal"),
        ("Fees", money_text(total_fees), "Approved schedule fees", "slate"),
        ("Total repayable", money_text(loan.total_repayable), f"{len(rows)} scheduled instalment(s)", "amber"),
    ], columns=2, styles=styles))
    story.append(callout(
        "Calculation basis",
        f"{_method_label(loan)} - {_rate_basis(loan)}. Each instalment below shows the full calculation and the resulting principal balance.",
        tone="blue",
        styles=styles,
    ))
    story.extend(section("Instalment calculations", "Read each card from the opening principal to the closing principal. Paid figures reflect the live LoanHub ledger.", styles=styles))
    actuals = _installment_by_number(loan)
    for row in rows:
        number = int(row.get("installment_number") or 0)
        story.append(_schedule_card(loan, row, actuals.get(number), include_formula=True))
        story.append(Spacer(1, 2.5 * mm))

    story.extend(section("Schedule reconciliation", styles=styles))
    story.append(metric_grid([
        ("Scheduled principal", money_text(sum((_money_from(row, "principal_due") for row in rows), Decimal("0"))), "Should equal approved principal", "blue"),
        ("Scheduled interest", money_text(total_interest), "Total charge for interest", "teal"),
        ("Scheduled fees", money_text(total_fees), "Fees distributed across the term", "slate"),
        ("Scheduled total", money_text(sum((_money_from(row, "total_due") for row in rows), Decimal("0"))), "Should equal total repayable", "green"),
    ], columns=2, styles=styles))
    story.append(callout(
        "Important",
        "This schedule does not replace an early-settlement quotation. Additional payments, reversals, lawful rescheduling or arrears may change the live balance and must be reflected by a new system-generated document.",
        tone="amber",
        styles=styles,
    ))
    return build_document(
        story=story,
        context=_document_context(db, loan, "Repayment Schedule"),
        title=f"Repayment Schedule {loan.loan_reference}",
        subject="Detailed repayment schedule and calculation explanation",
    )


def generate_payment_history_pdf(db: Session, loan: ClientCompanyLoan) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    payments = sorted(
        loan.payment_transactions,
        key=lambda item: item.completed_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    story.extend(hero_block(
        "Loan Payment History",
        "A chronological audit narrative of disbursements, repayments, references, receipts and instalment allocations.",
        loan.loan_reference,
        status=_loan_status(loan),
        styles=styles,
    ))
    inflows = sum((money(item.amount) for item in payments if humanize(item.direction).lower() == "inbound"), Decimal("0"))
    outflows = sum((money(item.amount) for item in payments if humanize(item.direction).lower() == "outbound"), Decimal("0"))
    story.append(metric_grid([
        ("Total received", money_text(inflows), "Successful inbound records", "green"),
        ("Total issued", money_text(outflows), "Successful outbound records", "blue"),
        ("Ledger paid", money_text(loan.amount_paid), "Allocated to the loan", "teal"),
        ("Outstanding", money_text(loan.balance), f"{len(payments)} transaction record(s)", "amber" if money(loan.balance) > 0 else "green"),
    ], columns=2, styles=styles))
    story.extend(section("Transaction timeline", "Each entry shows what happened, how it was recorded and where the amount was allocated.", styles=styles))

    if not payments:
        story.append(callout("No transactions", "No payment or disbursement transaction has been recorded for this loan.", tone="slate", styles=styles))
    for index, payment in enumerate(payments, start=1):
        receipt = db.query(PaymentReceipt).filter(PaymentReceipt.payment_id == payment.id).first()
        when = payment.completed_at or payment.created_at or datetime.now(timezone.utc)
        purpose = humanize(payment.purpose)
        status = humanize(payment.status)
        reference = payment.provider_reference or payment.proof_reference or str(payment.id)
        direction = humanize(payment.direction)
        method = humanize(payment.payment_method)
        allocations = (
            db.query(PaymentAllocation, RepaymentInstallment)
            .join(RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id)
            .filter(PaymentAllocation.payment_id == payment.id)
            .order_by(RepaymentInstallment.installment_number.asc())
            .all()
        )
        allocation_text = "No instalment allocation was attached to this transaction."
        if allocations:
            allocation_text = " ".join(
                f"{money_text(allocation.amount)} was applied to instalment {installment.installment_number} due {_date_value(installment.due_date)}."
                for allocation, installment in allocations
            )
        body = (
            f"LoanHub recorded <b>{money_text(payment.amount, payment.currency or 'LSL')}</b> as a <b>{escape(purpose)}</b> "
            f"through <b>{escape(method)}</b>. Direction: <b>{escape(direction)}</b>. Reference: <b>{escape(str(reference))}</b>. "
            f"Receipt/slip: <b>{escape(receipt.receipt_number if receipt else 'Not assigned')}</b>. {escape(allocation_text)}"
        )
        tone = "green" if status.lower() in {"succeeded", "completed", "paid"} else "red" if status.lower() in {"failed", "rejected"} else "blue"
        story.append(timeline_card(
            str(index),
            purpose,
            body,
            meta=when.strftime("%d %B %Y %H:%M UTC"),
            status=status,
            tone=tone,
            formula_lines=None,
            styles=styles,
        ))
        story.append(Spacer(1, 2.5 * mm))

    story.append(callout(
        "Document control",
        "Individual payment and disbursement slips remain the primary proof for each transaction. This payment history is a consolidated account record generated from the same FastAPI ledger.",
        tone="blue",
        styles=styles,
    ))
    return build_document(
        story=story,
        context=_document_context(db, loan, "Loan Payment History"),
        title=f"Payment History {loan.loan_reference}",
        subject="Chronological loan payment and disbursement history",
    )


def ensure_loan_document_file(db: Session, *, loan: ClientCompanyLoan, kind: str, content: bytes) -> None:
    store_bytes(
        db,
        content=content,
        original_name=f"{loan.loan_reference}-{kind}.pdf",
        mime_type="application/pdf",
        owner_user_id=loan.approved_by_user_id or loan.disbursed_by_user_id,
        company_id=loan.company_id,
        branch_id=loan.branch_id,
        category="loan_document",
        visibility="company",
        description=f"{kind.replace('-', ' ').title()} for {loan.loan_reference}",
        linked_entity_type="client_company_loan",
        linked_entity_id=str(loan.id),
        is_confidential=False,
    )


# ---------------------------------------------------------------------------
# Backward-compatible context renderers
# ---------------------------------------------------------------------------
# LoanHub originally exposed pure ``render_*`` helpers that accepted an already
# assembled document context. The production document flow now uses the richer
# ``generate_*`` functions above, which render directly from live loan models.
# Keeping these wrappers preserves compatibility with older integrations and
# regression tests without weakening the newer live-ledger document path.


def _legacy_document_context(context: dict[str, Any], title: str) -> DocumentContext:
    company_data = context.get("company") or {}
    loan_data = context.get("loan") or {}
    company = SimpleNamespace(
        id=None,
        name=safe_text(company_data.get("name"), "Loan company"),
        license_number=company_data.get("license_number"),
        registration_number=company_data.get("registration_number"),
        phone=company_data.get("phone"),
        email=company_data.get("email"),
        website=company_data.get("website"),
        address=company_data.get("address"),
        district=company_data.get("district"),
    )
    return DocumentContext(
        db=None,
        company=company,
        title=title,
        reference=safe_text(loan_data.get("reference"), "Loan document"),
    )


def _legacy_borrower_card(context: dict[str, Any], styles: dict[str, Any]):
    borrower = context.get("borrower") or {}
    return detail_card(
        "Borrower",
        [
            ("Name", safe_text(borrower.get("name"), "Borrower")),
            ("National ID", safe_text(borrower.get("national_id"))),
            ("Phone", safe_text(borrower.get("phone"))),
            ("Email", safe_text(borrower.get("email"))),
            ("Address", safe_text(borrower.get("address"))),
            ("Employment", safe_text(borrower.get("employment_status"))),
        ],
        tone="slate",
        styles=styles,
    )


def render_loan_information_pdf(context: dict[str, Any]) -> bytes:
    """Render a loan-information PDF from a prebuilt context.

    This is the compatibility entry point used by older LoanHub integrations.
    New application code should prefer ``generate_loan_information_pdf`` so the
    PDF is built directly from the live database-backed loan object.
    """
    styles = document_styles()
    loan = context.get("loan") or {}
    reference = safe_text(loan.get("reference"), "Loan")
    story: list[Any] = []
    story.extend(hero_block(
        "Loan Information Statement",
        "A concise account statement generated from the supplied LoanHub loan context.",
        reference,
        status=safe_text(loan.get("status")),
        styles=styles,
    ))
    story.append(metric_grid([
        ("Principal", money_text(loan.get("principal")), "Approved principal", "blue"),
        ("Total repayable", money_text(loan.get("total_repayable")), "Approved total", "teal"),
        ("Amount paid", money_text(loan.get("amount_paid")), "Recorded payments", "green"),
        ("Outstanding", money_text(loan.get("balance")), "Current balance", "amber"),
    ], columns=2, styles=styles))
    story.append(Spacer(1, 3 * mm))
    story.append(_legacy_borrower_card(context, styles))
    story.extend(section("Loan terms", styles=styles))
    story.append(detail_card(
        "Terms and dates",
        [
            ("Interest rate", f"{loan.get('interest_rate', 0)}%"),
            ("Processing fee", money_text(loan.get("processing_fee"))),
            ("Repayment type", safe_text(loan.get("repayment_type"))),
            ("Repayment period", safe_text(loan.get("repayment_period"))),
            ("First payment due", _date_value(loan.get("first_payment_due"))),
            ("Maturity date", _date_value(loan.get("maturity_date"))),
        ],
        tone="blue",
        styles=styles,
    ))

    schedule = context.get("schedule") or []
    story.extend(section("Repayment schedule", styles=styles))
    if not schedule:
        story.append(callout("No schedule available", "No repayment schedule was supplied in this document context.", tone="slate", styles=styles))
    for item in schedule:
        number = int(item.get("number") or item.get("installment_number") or 0)
        total = item.get("total", item.get("total_due", 0))
        paid = item.get("paid", item.get("paid_amount", 0))
        status = safe_text(item.get("status"), "Scheduled")
        story.append(timeline_card(
            str(number or "-"),
            f"Instalment {number or '-'}",
            (
                f"Due <b>{escape(_date_value(item.get('due_date')))}</b>. "
                f"Principal <b>{money_text(item.get('principal', item.get('principal_due', 0)))}</b>, "
                f"interest <b>{money_text(item.get('interest', item.get('interest_due', 0)))}</b>, "
                f"fees <b>{money_text(item.get('fees', item.get('fee_due', 0)))}</b>, "
                f"scheduled total <b>{money_text(total)}</b>, paid <b>{money_text(paid)}</b>."
            ),
            meta=f"Status: {status}",
            status=status,
            tone="green" if status.lower() == "paid" else "amber" if "overdue" in status.lower() else "blue",
            formula_lines=None,
            styles=styles,
        ))
        story.append(Spacer(1, 2 * mm))

    return build_document(
        story=story,
        context=_legacy_document_context(context, "Loan Information Statement"),
        title=f"Loan Information {reference}",
        subject="Loan information statement",
    )


def render_repayment_schedule_pdf(context: dict[str, Any]) -> bytes:
    """Render the legacy context-based repayment schedule PDF."""
    styles = document_styles()
    loan = context.get("loan") or {}
    reference = safe_text(loan.get("reference"), "Loan")
    schedule = context.get("schedule") or []
    story: list[Any] = []
    story.extend(hero_block(
        "Repayment Schedule",
        "Scheduled repayment dates, amounts and live status from the supplied LoanHub document context.",
        reference,
        status=safe_text(loan.get("status")),
        styles=styles,
    ))
    story.append(metric_grid([
        ("Principal", money_text(loan.get("principal")), "Original capital", "blue"),
        ("Instalment", money_text(loan.get("installment_amount")), "Expected instalment", "teal"),
        ("Total repayable", money_text(loan.get("total_repayable")), "Approved total", "amber"),
        ("Term", safe_text(loan.get("repayment_period")), safe_text(loan.get("repayment_type")), "slate"),
    ], columns=2, styles=styles))
    story.extend(section("Instalments", styles=styles))
    if not schedule:
        story.append(callout("No schedule available", "No repayment schedule was supplied in this document context.", tone="slate", styles=styles))
    for item in schedule:
        number = int(item.get("number") or item.get("installment_number") or 0)
        total = item.get("total", item.get("total_due", 0))
        paid = item.get("paid", item.get("paid_amount", 0))
        status = safe_text(item.get("status"), "Scheduled")
        story.append(timeline_card(
            str(number or "-"),
            f"Instalment {number or '-'} - {_date_value(item.get('due_date'))}",
            (
                f"Principal {money_text(item.get('principal', item.get('principal_due', 0)))}; "
                f"interest {money_text(item.get('interest', item.get('interest_due', 0)))}; "
                f"fees {money_text(item.get('fees', item.get('fee_due', 0)))}; "
                f"total {money_text(total)}; paid {money_text(paid)}."
            ),
            meta=f"Status: {status}",
            status=status,
            tone="green" if status.lower() == "paid" else "amber" if "overdue" in status.lower() else "blue",
            formula_lines=None,
            styles=styles,
        ))
        story.append(Spacer(1, 2 * mm))

    return build_document(
        story=story,
        context=_legacy_document_context(context, "Repayment Schedule"),
        title=f"Repayment Schedule {reference}",
        subject="Repayment schedule",
    )


def render_payment_history_pdf(context: dict[str, Any]) -> bytes:
    """Render the legacy context-based payment history PDF."""
    styles = document_styles()
    loan = context.get("loan") or {}
    reference = safe_text(loan.get("reference"), "Loan")
    payments = context.get("payments") or []
    story: list[Any] = []
    story.extend(hero_block(
        "Loan Payment History",
        "A chronological record of payment and disbursement activity supplied in the LoanHub document context.",
        reference,
        status=safe_text(loan.get("status")),
        styles=styles,
    ))
    story.append(metric_grid([
        ("Amount paid", money_text(loan.get("amount_paid")), "Loan ledger", "green"),
        ("Outstanding", money_text(loan.get("balance")), "Current balance", "amber"),
        ("Transactions", str(len(payments)), "Recorded entries", "blue"),
        ("Total repayable", money_text(loan.get("total_repayable")), "Approved total", "teal"),
    ], columns=2, styles=styles))
    story.extend(section("Transaction timeline", styles=styles))
    if not payments:
        story.append(callout("No transactions", "No payment or disbursement records were supplied in this document context.", tone="slate", styles=styles))
    for index, item in enumerate(payments, start=1):
        status = safe_text(item.get("status"), "Recorded")
        reference_value = item.get("reference") or item.get("provider_reference") or item.get("id") or "Not recorded"
        story.append(timeline_card(
            str(index),
            safe_text(item.get("purpose"), "Transaction"),
            (
                f"<b>{money_text(item.get('amount'))}</b> via <b>{escape(safe_text(item.get('method'), 'Not recorded'))}</b>. "
                f"Direction: <b>{escape(safe_text(item.get('direction')))}</b>. "
                f"Reference: <b>{escape(str(reference_value))}</b>. "
                f"Receipt: <b>{escape(safe_text(item.get('receipt_number'), 'Not issued'))}</b>."
            ),
            meta=_date_value(item.get("date")),
            status=status,
            tone="green" if status.lower() in {"succeeded", "completed", "paid"} else "red" if status.lower() in {"failed", "rejected"} else "blue",
            formula_lines=None,
            styles=styles,
        ))
        story.append(Spacer(1, 2 * mm))

    return build_document(
        story=story,
        context=_legacy_document_context(context, "Loan Payment History"),
        title=f"Payment History {reference}",
        subject="Loan payment history",
    )
