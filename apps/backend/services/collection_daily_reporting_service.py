from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib.units import mm
from reportlab.platypus import Spacer
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from database.config.config import settings
from database.models.branch import CompanyBranch
from database.models.chat import ChatConversation, ChatMessage, ChatMessageAttachment, ChatParticipant
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, LoanStatus, UserRole
from database.models.lending_operations import CollectionCase
from database.models.origination import BorrowerBankAccount, BorrowerKYCProfile
from database.models.reporting import GeneratedReport
from database.models.repayment import RepaymentInstallment
from services.crypto_service import encrypt_chat_text
from services.file_service import store_bytes
from services.lending_operations_service import make_reference, money, sync_overdue_collection_cases
from services.pdf_design_system import (
    CONTENT_WIDTH,
    DocumentContext,
    build_document,
    callout,
    detail_card,
    generated_timestamp,
    hero_block,
    metric_grid,
    money_text,
)
from services.reporting_service import report_reference

REPORT_TYPE = "missed_installments_daily"
REPORT_LOCK_ID = 62106420260729
SYSTEM_CONTEXT_TYPE = "collections_daily_alerts"


def _person(loan: ClientCompanyLoan):
    borrower = loan.borrower
    user = borrower.user if borrower else None
    return user.person if user else None


def _phone_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in {
                "phone",
                "phone_number",
                "mobile",
                "mobile_number",
                "contact",
                "contact_phone",
                "cell",
                "cellphone",
                "telephone",
            }:
                text_value = str(item or "").strip()
                if text_value:
                    values.append(text_value)
            elif isinstance(item, (dict, list, tuple)):
                values.extend(_phone_values(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            values.extend(_phone_values(item))
    return list(dict.fromkeys(values))


def _borrower_snapshot(db: Session, loan: ClientCompanyLoan) -> dict[str, Any]:
    borrower = loan.borrower
    user = borrower.user if borrower else None
    person = _person(loan)
    kyc = (
        db.query(BorrowerKYCProfile)
        .filter(
            BorrowerKYCProfile.company_id == loan.company_id,
            BorrowerKYCProfile.borrower_id == loan.borrower_id,
        )
        .first()
    )
    bank = (
        db.query(BorrowerBankAccount)
        .filter(
            BorrowerBankAccount.company_id == loan.company_id,
            BorrowerBankAccount.borrower_id == loan.borrower_id,
        )
        .first()
    )
    address_parts = [
        getattr(person, "physical_address", None),
        getattr(person, "town_or_village", None),
        getattr(person, "district", None),
    ]
    address = ", ".join(str(item).strip() for item in address_parts if item and str(item).strip())
    next_of_kin_phones = _phone_values(kyc.next_of_kin if kyc else {})
    emergency_phones = _phone_values(kyc.emergency_contact if kyc else {})

    return {
        "borrower_name": getattr(person, "full_name", None) or "Borrower",
        "phone": getattr(user, "phone", None),
        "email": getattr(user, "email", None),
        "physical_address": address or None,
        "next_of_kin_phones": next_of_kin_phones,
        "emergency_contact_phones": emergency_phones,
        "bank_name": getattr(bank, "bank_name", None),
        "bank_account_holder": getattr(bank, "account_holder", None),
        "bank_account_last4": getattr(bank, "account_number_last4", None),
        "masked_bank_account": (
            f"****{bank.account_number_last4}" if bank and bank.account_number_last4 else None
        ),
        "salary_account": bool(getattr(bank, "salary_account", False)) if bank else False,
    }


def _case_for_loan(db: Session, loan: ClientCompanyLoan) -> CollectionCase:
    case = (
        db.query(CollectionCase)
        .filter(
            CollectionCase.company_id == loan.company_id,
            CollectionCase.loan_id == loan.id,
        )
        .first()
    )
    if case:
        return case
    case = CollectionCase(
        company_id=loan.company_id,
        branch_id=loan.branch_id,
        borrower_id=loan.borrower_id,
        loan_id=loan.id,
        case_reference=make_reference("COL"),
        stage="early_arrears",
        days_past_due=1,
        overdue_amount=money(0),
        outstanding_balance=money(loan.balance),
        priority="normal",
    )
    db.add(case)
    db.flush()
    return case


def missed_installments(
    db: Session,
    *,
    company_id: UUID,
    due_date: date,
    branch_id: UUID | None = None,
) -> list[dict[str, Any]]:
    query = (
        db.query(RepaymentInstallment)
        .join(ClientCompanyLoan, ClientCompanyLoan.id == RepaymentInstallment.loan_id)
        .options(
            joinedload(RepaymentInstallment.loan)
            .joinedload(ClientCompanyLoan.borrower)
        )
        .filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
            ClientCompanyLoan.balance > 0,
            RepaymentInstallment.due_date == due_date,
            RepaymentInstallment.paid_amount < RepaymentInstallment.total_due,
        )
    )
    if branch_id is not None:
        query = query.filter(ClientCompanyLoan.branch_id == branch_id)
    else:
        query = query.filter(ClientCompanyLoan.branch_id.is_(None))

    rows: list[dict[str, Any]] = []
    for installment in query.order_by(RepaymentInstallment.installment_number.asc()).all():
        loan = installment.loan
        if not loan:
            continue
        shortfall = money(Decimal(installment.total_due or 0) - Decimal(installment.paid_amount or 0))
        if shortfall <= 0:
            continue
        case = _case_for_loan(db, loan)
        snapshot = _borrower_snapshot(db, loan)
        rows.append(
            {
                **snapshot,
                "case_id": case.id,
                "case_reference": case.case_reference,
                "loan_id": loan.id,
                "loan_reference": loan.loan_reference,
                "installment_id": installment.id,
                "installment_number": installment.installment_number,
                "due_date": installment.due_date,
                "expected_amount": money(installment.total_due),
                "paid_amount": money(installment.paid_amount),
                "shortfall": shortfall,
                "outstanding_balance": money(loan.balance),
                "branch_id": loan.branch_id,
            }
        )
    return rows


def _pdf_bytes(
    db: Session,
    *,
    company: LoanCompany,
    branch: CompanyBranch | None,
    due_date: date,
    rows: list[dict[str, Any]],
) -> bytes:
    styles = None
    total_shortfall = sum((Decimal(str(item["shortfall"])) for item in rows), Decimal("0"))
    total_expected = sum((Decimal(str(item["expected_amount"])) for item in rows), Decimal("0"))
    branch_name = branch.name if branch else "Company-wide / unassigned branch"
    story: list[Any] = []
    story.extend(
        hero_block(
            "Missed Payment Collections Report",
            "Internal collections report for instalments that were due on the previous business date and still had an unpaid balance when the report was generated.",
            due_date.isoformat(),
            status="confidential",
            styles=styles,
        )
    )
    story.append(
        metric_grid(
            [
                ("Borrowers requiring follow-up", str(len(rows)), branch_name, "amber"),
                ("Expected yesterday", money_text(total_expected), "Scheduled instalment total", "blue"),
                ("Unpaid shortfall", money_text(total_shortfall), "Amount still unpaid at report time", "red"),
                ("Scope", branch_name, "Company owner and branch manager alert", "slate"),
            ],
            columns=2,
        )
    )
    story.append(
        callout(
            "Collections control",
            "This is an internal follow-up report. It does not itself commence court or enforcement proceedings. Record each contact, visit, notice, court step or other action in the collections case screen.",
            tone="amber",
        )
    )
    story.append(
        callout(
            "Sensitive data",
            "Bank account numbers are masked in chat-delivered reports. Next-of-kin numbers are displayed for authorised internal follow-up only; do not disclose the borrower debt to a third party without a lawful or consent-based reason.",
            tone="slate",
        )
    )

    for index, item in enumerate(rows, start=1):
        kin = ", ".join(item["next_of_kin_phones"]) or "Not recorded"
        bank = "Not recorded"
        if item.get("bank_name") or item.get("masked_bank_account"):
            bank = " · ".join(
                value
                for value in [
                    str(item.get("bank_name") or "").strip(),
                    str(item.get("masked_bank_account") or "").strip(),
                ]
                if value
            )
        card = detail_card(
            f"{index}. {escape(str(item['borrower_name']))} · {escape(str(item['loan_reference']))}",
            [
                ("Collection case", escape(str(item["case_reference"]))),
                ("Instalment", f"#{item['installment_number']} due {item['due_date'].strftime('%d %B %Y')}"),
                ("Expected", money_text(item["expected_amount"])),
                ("Paid", money_text(item["paid_amount"])),
                ("Shortfall", money_text(item["shortfall"])),
                ("Loan balance", money_text(item["outstanding_balance"])),
                ("Borrower phone", escape(str(item.get("phone") or "Not recorded"))),
                ("Physical address", escape(str(item.get("physical_address") or "Not recorded"))),
                ("Next of kin phone(s)", escape(kin)),
                ("Bank", escape(bank)),
            ],
            tone="red",
            width=CONTENT_WIDTH,
        )
        story.append(card)
        story.append(Spacer(1, 2.5 * mm))

    return build_document(
        story=story,
        context=DocumentContext(
            db=db,
            company=company,
            title="Missed Payment Collections Report",
            reference=f"Due {due_date.isoformat()}",
            footer_note=generated_timestamp(),
            confidential=True,
        ),
        title=f"Missed Payment Report {due_date.isoformat()}",
        author=f"{company.name} via LoanHub",
        subject="Internal missed-payment collections report",
    )


def _recipient_staff(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
) -> list[CompanyStaff]:
    query = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == company_id,
        CompanyStaff.is_active.is_(True),
    )
    rows = query.filter(CompanyStaff.role == UserRole.COMPANY_OWNER).all()
    if branch_id is not None:
        rows.extend(
            query.filter(
                CompanyStaff.role == UserRole.BRANCH_MANAGER,
                CompanyStaff.branch_id == branch_id,
            ).all()
        )
    unique: dict[UUID, CompanyStaff] = {}
    for row in rows:
        unique[row.user_id] = row
    return list(unique.values())


def _collections_conversation(
    db: Session,
    *,
    company: LoanCompany,
    branch: CompanyBranch | None,
    recipients: list[CompanyStaff],
) -> ChatConversation | None:
    if not recipients:
        return None
    context_id = f"{company.id}:{branch.id if branch else 'company'}"
    conversation = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.company_id == company.id,
            ChatConversation.branch_id == (branch.id if branch else None),
            ChatConversation.context_type == SYSTEM_CONTEXT_TYPE,
            ChatConversation.context_id == context_id,
            ChatConversation.is_archived.is_(False),
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if not conversation:
        conversation = ChatConversation(
            reference=f"CHAT-{uuid.uuid4().hex[:10].upper()}",
            company_id=company.id,
            branch_id=branch.id if branch else None,
            created_by_user_id=None,
            title=f"Collections alerts · {branch.name if branch else company.name}",
            conversation_type="collections",
            context_type=SYSTEM_CONTEXT_TYPE,
            context_id=context_id,
            is_group=True,
            is_archived=False,
        )
        db.add(conversation)
        db.flush()

    expected_ids = {row.user_id for row in recipients}
    existing = {
        row.user_id: row
        for row in db.query(ChatParticipant)
        .filter(ChatParticipant.conversation_id == conversation.id)
        .all()
    }
    role_by_user = {row.user_id: row.role.value for row in recipients}
    for user_id, participant in existing.items():
        participant.is_active = user_id in expected_ids
    for user_id in expected_ids:
        if user_id in existing:
            existing[user_id].is_active = True
            existing[user_id].participant_role = role_by_user.get(user_id)
            continue
        db.add(
            ChatParticipant(
                conversation_id=conversation.id,
                user_id=user_id,
                participant_role=role_by_user.get(user_id),
                is_admin=role_by_user.get(user_id) == UserRole.COMPANY_OWNER.value,
                is_active=True,
                joined_at=now,
            )
        )
    return conversation


def _share_report_to_chat(
    db: Session,
    *,
    conversation: ChatConversation | None,
    report: GeneratedReport,
    row_count: int,
    total_shortfall: Decimal,
    due_date: date,
) -> tuple[UUID | None, UUID | None]:
    if not conversation or not report.file_id:
        return None, None
    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=None,
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
        message_type="file",
        client_message_id=f"collections-{due_date.isoformat()}-{report.id}",
        metadata_json={
            "system_generated": True,
            "report_type": REPORT_TYPE,
            "report_id": str(report.id),
        },
    )
    body = (
        f"Missed payment report for {due_date.isoformat()}: {row_count} borrower(s), "
        f"total unpaid shortfall {money_text(total_shortfall)}. Open the attached confidential PDF and record follow-up actions in Collections & legal."
    )
    ciphertext, nonce, version = encrypt_chat_text(body)
    message.body = None
    message.body_ciphertext = ciphertext
    message.body_nonce = nonce
    message.encryption_version = version
    db.add(message)
    db.flush()
    db.add(ChatMessageAttachment(message_id=message.id, file_id=report.file_id))
    conversation.last_message_at = datetime.now(timezone.utc)
    return conversation.id, message.id


def _existing_report(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    due_date: date,
) -> GeneratedReport | None:
    query = db.query(GeneratedReport).filter(
        GeneratedReport.report_type == REPORT_TYPE,
        GeneratedReport.output_format == "pdf",
        GeneratedReport.company_id == company_id,
        GeneratedReport.period_start == due_date,
        GeneratedReport.period_end == due_date,
    )
    if branch_id is None:
        query = query.filter(GeneratedReport.branch_id.is_(None))
    else:
        query = query.filter(GeneratedReport.branch_id == branch_id)
    return query.order_by(GeneratedReport.generated_at.desc()).first()


def generate_scope_report(
    db: Session,
    *,
    company: LoanCompany,
    branch: CompanyBranch | None,
    due_date: date,
) -> GeneratedReport | None:
    existing = _existing_report(
        db,
        company_id=company.id,
        branch_id=branch.id if branch else None,
        due_date=due_date,
    )
    if existing:
        return existing

    rows = missed_installments(
        db,
        company_id=company.id,
        branch_id=branch.id if branch else None,
        due_date=due_date,
    )
    if not rows:
        return None

    total_shortfall = sum((Decimal(str(item["shortfall"])) for item in rows), Decimal("0"))
    content = _pdf_bytes(db, company=company, branch=branch, due_date=due_date, rows=rows)
    recipients = _recipient_staff(
        db,
        company_id=company.id,
        branch_id=branch.id if branch else None,
    )
    owner_user_id = recipients[0].user_id if recipients else None
    report = GeneratedReport(
        reference=report_reference(),
        scope_type="branch" if branch else "company",
        company_id=company.id,
        branch_id=branch.id if branch else None,
        generated_by_user_id=None,
        title=f"Missed payments · {branch.name if branch else company.name} · {due_date.isoformat()}",
        report_type=REPORT_TYPE,
        output_format="pdf",
        period_start=due_date,
        period_end=due_date,
        status="completed",
        metrics={
            "row_count": len(rows),
            "total_shortfall": str(total_shortfall),
            "due_date": due_date.isoformat(),
        },
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.flush()
    stored = store_bytes(
        db,
        content=content,
        original_name=f"missed-payments-{due_date.isoformat()}-{branch.id if branch else 'company'}.pdf",
        mime_type="application/pdf",
        owner_user_id=owner_user_id,
        company_id=company.id,
        branch_id=branch.id if branch else None,
        category="collection_report",
        visibility="company",
        description=f"Confidential missed-payment report for {due_date.isoformat()}",
        linked_entity_type="generated_report",
        linked_entity_id=str(report.id),
        is_confidential=True,
    )
    report.file_id = stored.id
    conversation = _collections_conversation(
        db,
        company=company,
        branch=branch,
        recipients=recipients,
    )
    conversation_id, message_id = _share_report_to_chat(
        db,
        conversation=conversation,
        report=report,
        row_count=len(rows),
        total_shortfall=total_shortfall,
        due_date=due_date,
    )
    metrics = dict(report.metrics or {})
    metrics.update(
        {
            "chat_conversation_id": str(conversation_id) if conversation_id else None,
            "chat_message_id": str(message_id) if message_id else None,
            "recipient_count": len(recipients),
        }
    )
    report.metrics = metrics
    db.commit()
    db.refresh(report)
    return report


def generate_company_reports(
    db: Session,
    *,
    company_id: UUID,
    due_date: date,
    branch_id: UUID | None = None,
) -> list[GeneratedReport]:
    company = db.get(LoanCompany, company_id)
    if not company or not company.is_active:
        return []
    sync_overdue_collection_cases(db, company_id)

    reports: list[GeneratedReport] = []
    if branch_id is not None:
        branch = db.get(CompanyBranch, branch_id)
        if branch and branch.company_id == company_id and branch.is_active:
            report = generate_scope_report(db, company=company, branch=branch, due_date=due_date)
            if report:
                reports.append(report)
        return reports

    # Generate branch-specific reports first.
    branch_ids = {
        row[0]
        for row in (
            db.query(ClientCompanyLoan.branch_id)
            .join(RepaymentInstallment, RepaymentInstallment.loan_id == ClientCompanyLoan.id)
            .filter(
                ClientCompanyLoan.company_id == company_id,
                ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
                ClientCompanyLoan.balance > 0,
                RepaymentInstallment.due_date == due_date,
                RepaymentInstallment.paid_amount < RepaymentInstallment.total_due,
                ClientCompanyLoan.branch_id.is_not(None),
            )
            .distinct()
            .all()
        )
    }
    for current_branch_id in branch_ids:
        branch = db.get(CompanyBranch, current_branch_id)
        if branch and branch.is_active:
            report = generate_scope_report(db, company=company, branch=branch, due_date=due_date)
            if report:
                reports.append(report)

    # Keep a company-owner-only report for loans that are not linked to a branch.
    unassigned = generate_scope_report(db, company=company, branch=None, due_date=due_date)
    if unassigned:
        reports.append(unassigned)
    return reports


def run_missed_payment_reporting(
    db: Session,
    *,
    local_date: date | None = None,
) -> dict[str, int]:
    if not settings.COLLECTION_DAILY_REPORT_ENABLED:
        return {"generated": 0, "skipped": 0}
    acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": REPORT_LOCK_ID},
    ).scalar()
    if not acquired:
        return {"generated": 0, "skipped": 1}

    current_date = local_date or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    due_date = current_date - timedelta(days=1)
    companies = db.query(LoanCompany).filter(
        LoanCompany.status == CompanyStatus.APPROVED,
        LoanCompany.is_active.is_(True),
    ).all()
    generated = 0
    for company in companies:
        before = db.query(GeneratedReport.id).filter(
            GeneratedReport.company_id == company.id,
            GeneratedReport.report_type == REPORT_TYPE,
            GeneratedReport.period_start == due_date,
            GeneratedReport.period_end == due_date,
        ).count()
        reports = generate_company_reports(db, company_id=company.id, due_date=due_date)
        after = db.query(GeneratedReport.id).filter(
            GeneratedReport.company_id == company.id,
            GeneratedReport.report_type == REPORT_TYPE,
            GeneratedReport.period_start == due_date,
            GeneratedReport.period_end == due_date,
        ).count()
        generated += max(after - before, 0)
        # `reports` is intentionally materialized so all scopes run even when some already exist.
        _ = reports
    return {"generated": generated, "skipped": 0}
