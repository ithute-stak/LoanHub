from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from database.config.config import settings

from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import (
    InstallmentStatus,
    LoanRequestStatus,
    LoanStatus,
    OfferStatus,
    SubscriptionStatus,
)
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.repayment import RepaymentInstallment
from database.models.subscription import CompanySubscription
from services.reporting_service import run_due_report_schedules
from services.maturity_recovery_service import process_maturity_renewals, process_collection_reminders


@dataclass(slots=True)
class MaintenanceResult:
    expired_requests: int = 0
    expired_offers: int = 0
    expired_subscriptions: int = 0
    overdue_installments: int = 0
    overdue_loans: int = 0
    completed_loans: int = 0
    maturity_renewals: int = 0
    maturity_collections_started: int = 0
    collection_reminders: int = 0
    generated_reports: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def run_maintenance(db: Session) -> MaintenanceResult:
    """Reconcile time-dependent records through normal ORM changes.

    Using mapped instances instead of bulk UPDATE statements is intentional:
    LoanHub's transparency listeners can then audit the changes, persist
    role-targeted notifications, and deliver live events after commit.
    """

    now = datetime.now(timezone.utc)
    today = datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    result = MaintenanceResult()

    requests = (
        db.query(LoanRequest)
        .filter(
            LoanRequest.status.in_(
                [LoanRequestStatus.OPEN, LoanRequestStatus.OFFERED]
            ),
            LoanRequest.expires_at.is_not(None),
            LoanRequest.expires_at < now,
        )
        .all()
    )
    for request in requests:
        request.status = LoanRequestStatus.EXPIRED
        request.visible_to_lenders = False
    result.expired_requests = len(requests)

    offers = (
        db.query(LoanOffer)
        .filter(
            LoanOffer.status == OfferStatus.PENDING,
            LoanOffer.expires_at.is_not(None),
            LoanOffer.expires_at < now,
        )
        .all()
    )
    for offer in offers:
        offer.status = OfferStatus.EXPIRED
    result.expired_offers = len(offers)

    # Renew matured balances before the ordinary overdue pass. Superseded
    # installments are historical evidence and must never be marked overdue or
    # sent to collections after their balance has been capitalised.
    maturity = process_maturity_renewals(db, today=today)
    result.maturity_renewals = maturity["renewed"]
    result.maturity_collections_started = maturity["collections_started"]

    subscriptions = (
        db.query(CompanySubscription)
        .filter(
            CompanySubscription.status == SubscriptionStatus.ACTIVE,
            CompanySubscription.end_date < today,
        )
        .all()
    )
    for subscription in subscriptions:
        subscription.status = SubscriptionStatus.EXPIRED
        subscription.auto_renew = False
    result.expired_subscriptions = len(subscriptions)

    # Reconcile both directions. Previously the maintenance pass only set overdue
    # to True and never cleared it when a late installment was subsequently paid.
    eligible_loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.balance > 0,
            ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        )
        .all()
    )
    active_loan_ids = {loan.id for loan in eligible_loans}
    active_installments = (
        db.query(RepaymentInstallment)
        .filter(
            RepaymentInstallment.loan_id.in_(active_loan_ids),
            RepaymentInstallment.is_superseded.is_(False),
        )
        .all()
    ) if active_loan_ids else []

    overdue_loan_ids = set()
    overdue_installment_count = 0
    for installment in active_installments:
        if installment.status in {InstallmentStatus.WAIVED, InstallmentStatus.PAID}:
            continue
        remaining = (installment.total_due or 0) - (installment.paid_amount or 0)
        is_late = remaining > 0 and installment.due_date < today
        if is_late:
            overdue_loan_ids.add(installment.loan_id)
            overdue_installment_count += 1
            if installment.status != InstallmentStatus.OVERDUE:
                installment.status = InstallmentStatus.OVERDUE
        elif installment.status == InstallmentStatus.OVERDUE:
            installment.status = (
                InstallmentStatus.PARTIALLY_PAID
                if (installment.paid_amount or 0) > 0
                else InstallmentStatus.PENDING
            )
    result.overdue_installments = overdue_installment_count

    for loan in eligible_loans:
        loan.is_overdue = loan.id in overdue_loan_ids
    # Also clear flags on all other loans (settled, pending, cancelled, etc.).
    stale_loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.is_overdue.is_(True),
            ClientCompanyLoan.id.notin_(active_loan_ids),
        )
        .all()
    ) if active_loan_ids else db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.is_overdue.is_(True)
    ).all()
    for loan in stale_loans:
        loan.is_overdue = False
    result.overdue_loans = len(overdue_loan_ids)

    settled_loans = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.balance <= 0)
        .all()
    )
    completed_transitions = 0
    for loan in settled_loans:
        if loan.status not in {
            LoanStatus.COMPLETED,
            LoanStatus.CANCELLED,
            LoanStatus.REJECTED,
        }:
            loan.status = LoanStatus.COMPLETED
            completed_transitions += 1
        loan.is_overdue = False
    result.completed_loans = completed_transitions

    result.collection_reminders = process_collection_reminders(db, now=now)
    result.generated_reports = run_due_report_schedules(db)

    db.commit()
    return result
