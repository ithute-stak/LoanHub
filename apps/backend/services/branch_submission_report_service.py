from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from database.models.branch import CompanyBranch
from database.models.company import LoanCompany
from database.models.file_management import ManagedFile
from database.models.treasury import BranchDailyLedger, BranchDailySubmission, BranchOpeningSource, TreasuryEntry
from services.file_service import store_bytes


def _money(value: object) -> str:
    return f"LSL {Decimal(str(value or 0)):,.2f}"


def _title(value: object) -> str:
    raw = value.value if hasattr(value, "value") else str(value or "")
    return raw.replace("_", " ").title()


def _small_table(rows: list[list[object]], widths: list[float] | None = None, repeat_rows: int = 0) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=repeat_rows)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3d56")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(16 * mm, 13 * mm, 194 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(16 * mm, 8.5 * mm, "LoanHub branch submission report · Generated and stored in Files")
    canvas.drawRightString(194 * mm, 8.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_branch_submission_pdf(
    db: Session,
    submission: BranchDailySubmission,
) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from services.pdf_design_system import (
        DocumentContext,
        build_document,
        callout,
        detail_card,
        document_styles,
        generated_timestamp,
        hero_block,
        metric_grid,
        money_text,
        section,
        timeline_card,
        two_card_row,
    )

    company = db.get(LoanCompany, submission.company_id)
    branch = db.get(CompanyBranch, submission.branch_id)
    headquarters = db.get(CompanyBranch, submission.submitted_to_branch_id) if submission.submitted_to_branch_id else None
    ledger = (
        db.query(BranchDailyLedger)
        .options(
            joinedload(BranchDailyLedger.entries).joinedload(TreasuryEntry.expense_category),
            joinedload(BranchDailyLedger.opening_sources),
        )
        .filter(BranchDailyLedger.id == submission.daily_ledger_id)
        .first()
    )
    entries: Iterable[TreasuryEntry] = ledger.entries if ledger else []
    sources: Iterable[BranchOpeningSource] = ledger.opening_sources if ledger else []
    valid_entries = [entry for entry in entries if not entry.is_voided]
    confirmed_sources = [source for source in sources if source.is_confirmed and not source.is_voided]

    company_name = company.name if company else "LoanHub lending company"
    branch_name = branch.name if branch else str(submission.branch_id)
    report_reference = f"BDS-{submission.business_date:%Y%m%d}-{submission.sequence_number:03d}-{str(submission.id)[:8].upper()}"
    styles = document_styles()
    story: list[object] = []
    story.extend(hero_block(
        "Daily Branch Accounting Submission",
        "A frozen management record explaining opening funds, money movements, expenses, closing balance and reconciliation exceptions.",
        report_reference,
        status="locked snapshot",
        styles=styles,
    ))

    scope_card = detail_card(
        "Submission identity",
        [
            ("Company", company_name),
            ("Branch", branch_name),
            ("Submitted to", headquarters.name if headquarters else "Headquarters not configured"),
            ("Business date", submission.business_date.strftime("%d %B %Y")),
            ("Sequence", str(submission.sequence_number)),
        ],
        tone="blue",
    )
    control_card = detail_card(
        "Document control",
        [
            ("Submitted at", submission.submitted_at.strftime("%d %B %Y %H:%M UTC")),
            ("Mode", "Automatic" if submission.is_automatic else "Manual"),
            ("Included entries", str(submission.entry_count)),
            ("Pending excluded", str(submission.pending_entry_count)),
            ("Status", "Locked snapshot"),
        ],
        tone="slate",
    )
    story.append(two_card_row(scope_card, control_card))
    story.append(Spacer(1, 4 * mm))

    variance = Decimal(str(submission.variance_amount or 0))
    story.extend(section("Daily money reconciliation", "The reconciliation explains the expected closing balance before comparing it with the branch declaration.", styles=styles))
    story.append(metric_grid([
        ("Opening balance", money_text(submission.opening_balance), "Confirmed opening funds", "slate"),
        ("Money in", money_text(submission.total_money_in), "Collections and other inflows", "green"),
        ("Money out", money_text(submission.total_money_out), "Disbursements and operating costs", "red"),
        ("Expected closing", money_text(submission.closing_balance), "Opening + inflows - outflows", "blue"),
        ("Declared closing", money_text(submission.declared_closing_balance), "Amount declared by the branch", "teal"),
        ("Variance", money_text(submission.variance_amount), "Declared less expected", "green" if variance == 0 else "red"),
    ], columns=2, styles=styles))
    story.append(callout(
        "Reconciliation formula",
        f"Opening {money_text(submission.opening_balance)} + money in {money_text(submission.total_money_in)} - money out {money_text(submission.total_money_out)} = expected closing {money_text(submission.closing_balance)}. "
        f"The branch declared {money_text(submission.declared_closing_balance)}, producing a variance of {money_text(submission.variance_amount)}.",
        tone="green" if variance == 0 else "red",
        styles=styles,
    ))

    story.extend(section("Opening funding sources", "Only confirmed and non-voided opening sources are included.", styles=styles))
    if not confirmed_sources:
        story.append(callout("No confirmed sources", "No confirmed opening-balance sources were attached to this ledger.", tone="slate", styles=styles))
    for index, source in enumerate(sorted(confirmed_sources, key=lambda row: (str(row.source_type), row.created_at)), start=1):
        body = (
            f"The branch opened the day with <b>{money_text(source.amount)}</b> from <b>{_title(source.source_type)}</b>. "
            f"Description: <b>{source.description or 'Not recorded'}</b>. Channel: <b>{_title(source.payment_method)}</b>. "
            f"Reference: <b>{source.source_reference or 'Not recorded'}</b>."
        )
        story.append(timeline_card(str(index), _title(source.source_type), body, status="confirmed", tone="green", styles=styles))
        story.append(Spacer(1, 2 * mm))

    story.extend(section("Payment-channel movement", "Each channel is summarised as an inflow, outflow and net position rather than a dense table.", styles=styles))
    channel_totals = submission.channel_totals or {}
    if not channel_totals:
        story.append(callout("No channel totals", "No payment-channel totals were recorded for this submission.", tone="slate", styles=styles))
    for index, (key, value) in enumerate(sorted(channel_totals.items()), start=1):
        data = value if isinstance(value, dict) else {}
        net = Decimal(str(data.get("net", 0) or 0))
        body = (
            f"<b>{_title(key)}</b> received <b>{money_text(data.get('money_in', 0))}</b> and paid out "
            f"<b>{money_text(data.get('money_out', 0))}</b>. Net movement was <b>{money_text(net)}</b> across "
            f"<b>{data.get('entry_count', 0)}</b> posted entries."
        )
        story.append(timeline_card(str(index), _title(key), body, status="positive" if net >= 0 else "negative", tone="green" if net >= 0 else "amber", styles=styles))
        story.append(Spacer(1, 2 * mm))

    category_names = {
        str(entry.expense_category_id): entry.expense_category.name
        for entry in valid_entries if entry.expense_category_id and entry.expense_category
    }
    expense_totals = submission.expense_totals or {}
    story.extend(section("Expense analysis", "Posted expenses are grouped by category and linked back to the detailed movement narrative.", styles=styles))
    if not expense_totals:
        story.append(callout("No posted expenses", "No approved operating expenses were included in this submission.", tone="green", styles=styles))
    else:
        expense_items = [
            (category_names.get(str(key), _title(key)), money_text(value), "Posted category total", "amber")
            for key, value in sorted(expense_totals.items())
        ]
        story.append(metric_grid(expense_items, columns=2, styles=styles))

    story.extend(section("Detailed movement narrative", "Entries are shown in chronological order with the transaction purpose, channel, proof and approval status.", styles=styles))
    if not valid_entries:
        story.append(callout("No movements", "No non-voided treasury movements were attached to this submission.", tone="slate", styles=styles))
    for index, entry in enumerate(sorted(valid_entries, key=lambda row: (row.occurred_at, row.created_at)), start=1):
        direction = _title(entry.direction)
        status = _title(entry.approval_status)
        body = (
            f"At <b>{entry.occurred_at.strftime('%H:%M')}</b>, the branch recorded <b>{money_text(entry.amount)}</b> as "
            f"<b>{_title(entry.entry_type)}</b> moving <b>{direction.lower()}</b>. Description: <b>{entry.description or 'Not recorded'}</b>. "
            f"Channel: <b>{_title(entry.payment_method)}</b>. Proof/reference: <b>{entry.proof_reference or 'Not recorded'}</b>."
        )
        tone = "green" if direction.lower() == "money in" else "amber" if direction.lower() == "money out" else "blue"
        if status.lower() in {"rejected", "failed"}:
            tone = "red"
        story.append(timeline_card(str(index), _title(entry.entry_type), body, meta=entry.occurred_at.strftime("%d %B %Y %H:%M"), status=status, tone=tone, styles=styles))
        story.append(Spacer(1, 2 * mm))

    notes = submission.notes or "No submission notes were recorded."
    story.extend(section("Submission notes and sign-off", styles=styles))
    story.append(callout("Branch notes", notes.replace("\n", "<br/>"), tone="blue", styles=styles))
    story.append(Spacer(1, 4 * mm))
    signoff_left = detail_card(
        "Branch confirmation",
        [
            ("Manager / finance name", "____________________________"),
            ("Signature", "____________________________"),
            ("Date", "____________________________"),
        ],
        tone="slate",
    )
    signoff_right = detail_card(
        "Headquarters review",
        [
            ("Reviewer name", "____________________________"),
            ("Signature", "____________________________"),
            ("Date", "____________________________"),
        ],
        tone="slate",
    )
    story.append(two_card_row(signoff_left, signoff_right))
    story.append(Spacer(1, 3 * mm))
    story.append(callout(
        "Frozen numbered submission",
        "Later corrections create a new sequence. This document must not be edited because it represents the numbered financial snapshot submitted for the stated business date.",
        tone="amber",
        styles=styles,
    ))

    context = DocumentContext(
        db=db,
        company=company,
        title="Daily Branch Accounting Submission",
        reference=report_reference,
        footer_note=generated_timestamp(),
        confidential=True,
    )
    return build_document(
        story=story,
        context=context,
        title=f"Branch submission {submission.business_date} sequence {submission.sequence_number}",
        author=f"{company_name} via LoanHub",
        subject="Daily branch money, expense and accounting submission",
    )

def ensure_branch_submission_pdf(db: Session, submission: BranchDailySubmission, *, force: bool = False) -> ManagedFile:
    if submission.pdf_file_id and not force:
        existing = db.get(ManagedFile, submission.pdf_file_id)
        if existing:
            return existing
    content = build_branch_submission_pdf(db, submission)
    report_reference = f"BDS-{submission.business_date:%Y%m%d}-{submission.sequence_number:03d}-{str(submission.id)[:8].upper()}"
    managed = store_bytes(
        db,
        content=content,
        original_name=f"{report_reference}.pdf",
        mime_type="application/pdf",
        owner_user_id=submission.submitted_by_user_id,
        company_id=submission.company_id,
        branch_id=submission.branch_id,
        category="branch_submission_report",
        visibility="company",
        description=f"Branch daily submission for {submission.business_date} sequence {submission.sequence_number}",
        linked_entity_type="branch_daily_submission",
        linked_entity_id=str(submission.id),
        is_confidential=True,
    )
    submission.pdf_file_id = managed.id
    db.flush()
    return managed
