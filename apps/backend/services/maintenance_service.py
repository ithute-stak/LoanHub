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

    installments = (
        db.query(RepaymentInstallment)
        .filter(
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.status.in_(
                [
                    InstallmentStatus.PENDING,
                    InstallmentStatus.PARTIALLY_PAID,
                ]
            ),
            RepaymentInstallment.due_date < today,
        )
        .all()
    )
    overdue_loan_ids = set()
    for installment in installments:
        installment.status = InstallmentStatus.OVERDUE
        overdue_loan_ids.add(installment.loan_id)
    result.overdue_installments = len(installments)

    overdue_loans = []
    if overdue_loan_ids:
        overdue_loans = (
            db.query(ClientCompanyLoan)
            .filter(
                ClientCompanyLoan.id.in_(overdue_loan_ids),
                ClientCompanyLoan.status.in_(
                    [LoanStatus.ACTIVE, LoanStatus.APPROVED]
                ),
                ClientCompanyLoan.is_overdue.is_(False),
            )
            .all()
        )
        for loan in overdue_loans:
            loan.is_overdue = True
    result.overdue_loans = len(overdue_loans)

    completed_loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.balance <= 0,
            ClientCompanyLoan.status.notin_(
                [
                    LoanStatus.COMPLETED,
                    LoanStatus.CANCELLED,
                    LoanStatus.REJECTED,
                ]
            ),
        )
        .all()
    )
    for loan in completed_loans:
        loan.status = LoanStatus.COMPLETED
        loan.is_overdue = False
    result.completed_loans = len(completed_loans)

    result.collection_reminders = process_collection_reminders(db, now=now)
    result.generated_reports = run_due_report_schedules(db)

    db.commit()
    return result
