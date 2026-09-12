from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from database.models.branch import CompanyBranch
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.employee import PerformanceGoal, PerformanceReview
from database.models.enums import LoanStatus, OfferStatus, PaymentStatus
from database.models.loan_offer import LoanOffer
from database.models.payment import PaymentTransaction
from database.models.user import User
from database.schemas.performance import (
    BranchPerformanceRead,
    CompanyPerformanceRead,
    EmployeePerformanceRead,
    PerformanceOverviewRead,
)


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _person_name(staff: CompanyStaff) -> str:
    person = staff.user.person if staff.user else None
    if person:
        return person.full_name
    if staff.user:
        return staff.user.email or staff.user.phone or "Employee"
    return "Employee"


def _employee_rows(
    db: Session,
    *,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> list[EmployeePerformanceRead]:
    staff_query = db.query(CompanyStaff).options(
        joinedload(CompanyStaff.user).joinedload(User.person),
        joinedload(CompanyStaff.employee_profile),
    ).filter(CompanyStaff.is_active.is_(True))

    if company_id:
        staff_query = staff_query.filter(CompanyStaff.company_id == company_id)
    if branch_id:
        staff_query = staff_query.filter(CompanyStaff.branch_id == branch_id)

    staff_items = staff_query.all()
    if not staff_items:
        return []

    user_ids = [staff.user_id for staff in staff_items]
    profile_ids = [
        staff.employee_profile.id
        for staff in staff_items
        if staff.employee_profile
    ]

    offer_query = db.query(
        LoanOffer.offered_by_user_id,
        func.count(LoanOffer.id),
        func.coalesce(
            func.sum(
                case(
                    (LoanOffer.status == OfferStatus.ACCEPTED, 1),
                    else_=0,
                )
            ),
            0,
        ),
    ).filter(LoanOffer.offered_by_user_id.in_(user_ids))
    if company_id:
        offer_query = offer_query.filter(LoanOffer.company_id == company_id)
    if branch_id:
        offer_query = offer_query.filter(LoanOffer.branch_id == branch_id)
    offer_metrics = {
        user_id: (int(created or 0), int(accepted or 0))
        for user_id, created, accepted in offer_query.group_by(
            LoanOffer.offered_by_user_id
        ).all()
    }

    approved_query = db.query(
        ClientCompanyLoan.approved_by_user_id,
        func.count(ClientCompanyLoan.id),
    ).filter(ClientCompanyLoan.approved_by_user_id.in_(user_ids))
    disbursed_query = db.query(
        ClientCompanyLoan.disbursed_by_user_id,
        func.count(ClientCompanyLoan.id),
    ).filter(ClientCompanyLoan.disbursed_by_user_id.in_(user_ids))
    if company_id:
        approved_query = approved_query.filter(ClientCompanyLoan.company_id == company_id)
        disbursed_query = disbursed_query.filter(ClientCompanyLoan.company_id == company_id)
    if branch_id:
        approved_query = approved_query.filter(ClientCompanyLoan.branch_id == branch_id)
        disbursed_query = disbursed_query.filter(ClientCompanyLoan.branch_id == branch_id)
    approved_metrics = {
        user_id: int(count or 0)
        for user_id, count in approved_query.group_by(
            ClientCompanyLoan.approved_by_user_id
        ).all()
    }
    disbursed_metrics = {
        user_id: int(count or 0)
        for user_id, count in disbursed_query.group_by(
            ClientCompanyLoan.disbursed_by_user_id
        ).all()
    }

    payment_query = db.query(
        PaymentTransaction.initiated_by_user_id,
        func.count(PaymentTransaction.id),
        func.coalesce(
            func.sum(
                case(
                    (
                        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
                        PaymentTransaction.amount,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
    ).filter(PaymentTransaction.initiated_by_user_id.in_(user_ids))
    if company_id:
        payment_query = payment_query.filter(PaymentTransaction.company_id == company_id)
    if branch_id:
        payment_query = payment_query.join(
            ClientCompanyLoan,
            ClientCompanyLoan.id == PaymentTransaction.loan_id,
        ).filter(ClientCompanyLoan.branch_id == branch_id)
    payment_metrics = {
        user_id: (int(count or 0), _decimal(amount))
        for user_id, count, amount in payment_query.group_by(
            PaymentTransaction.initiated_by_user_id
        ).all()
    }

    goals_by_employee: dict[UUID, list[PerformanceGoal]] = defaultdict(list)
    if profile_ids:
        for goal in db.query(PerformanceGoal).filter(
            PerformanceGoal.employee_id.in_(profile_ids)
        ).all():
            goals_by_employee[goal.employee_id].append(goal)

    review_average = {}
    if profile_ids:
        review_average = {
            employee_id: float(average or 0)
            for employee_id, average in db.query(
                PerformanceReview.employee_id,
                func.coalesce(func.avg(PerformanceReview.overall_score), 0),
            ).filter(
                PerformanceReview.employee_id.in_(profile_ids)
            ).group_by(PerformanceReview.employee_id).all()
        }

    rows: list[EmployeePerformanceRead] = []
    for staff in staff_items:
        profile = staff.employee_profile
        offers_created, offers_accepted = offer_metrics.get(staff.user_id, (0, 0))
        loans_approved = approved_metrics.get(staff.user_id, 0)
        loans_disbursed = disbursed_metrics.get(staff.user_id, 0)
        payment_transactions, successful_payment_amount = payment_metrics.get(
            staff.user_id,
            (0, Decimal("0")),
        )

        goals = goals_by_employee.get(profile.id, []) if profile else []
        active_goals = sum(1 for goal in goals if goal.status == "active")
        completed_goals = sum(1 for goal in goals if goal.status == "completed")
        goal_completion = 0.0
        if goals:
            percentages = [
                min(
                    100.0,
                    float(
                        _decimal(goal.current_value)
                        / max(_decimal(goal.target_value), Decimal("0.001"))
                        * 100
                    ),
                )
                for goal in goals
            ]
            goal_completion = sum(percentages) / len(percentages)

        average_review = review_average.get(profile.id, 0.0) if profile else 0.0
        offer_conversion = (
            offers_accepted / offers_created * 100
            if offers_created
            else 0
        )
        activity_score = min(
            100.0,
            (offers_created * 4)
            + (loans_approved * 8)
            + (loans_disbursed * 10),
        )
        payment_score = min(100.0, payment_transactions * 8)
        review_component = average_review if average_review else 50.0
        goal_component = goal_completion if profile else 50.0
        performance_score = round(
            offer_conversion * 0.20
            + activity_score * 0.25
            + payment_score * 0.20
            + goal_component * 0.20
            + review_component * 0.15,
            2,
        )

        rows.append(
            EmployeePerformanceRead(
                staff_id=staff.id,
                employee_id=profile.id if profile else None,
                user_id=staff.user_id,
                branch_id=staff.branch_id,
                employee_name=_person_name(staff),
                role=staff.role.value,
                job_title=profile.job_title if profile else None,
                department=profile.department if profile else None,
                offers_created=offers_created,
                offers_accepted=offers_accepted,
                loans_approved=loans_approved,
                loans_disbursed=loans_disbursed,
                payment_transactions=payment_transactions,
                successful_payment_amount=successful_payment_amount,
                active_goals=active_goals,
                completed_goals=completed_goals,
                goal_completion_percent=round(goal_completion, 2),
                average_review_score=round(average_review, 2),
                performance_score=performance_score,
            )
        )

    return sorted(rows, key=lambda item: item.performance_score, reverse=True)


def build_performance_overview(
    db: Session,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> PerformanceOverviewRead:
    employees = _employee_rows(
        db,
        company_id=company_id,
        branch_id=branch_id,
    )

    company_query = db.query(LoanCompany)
    branch_query = db.query(CompanyBranch)
    loan_query = db.query(ClientCompanyLoan)
    payment_query = db.query(PaymentTransaction).filter(
        PaymentTransaction.status == PaymentStatus.SUCCEEDED
    )

    if company_id:
        company_query = company_query.filter(LoanCompany.id == company_id)
        branch_query = branch_query.filter(CompanyBranch.company_id == company_id)
        loan_query = loan_query.filter(ClientCompanyLoan.company_id == company_id)
        payment_query = payment_query.filter(PaymentTransaction.company_id == company_id)
    if branch_id:
        branch_query = branch_query.filter(CompanyBranch.id == branch_id)
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == branch_id)
        payment_query = payment_query.join(
            ClientCompanyLoan,
            ClientCompanyLoan.id == PaymentTransaction.loan_id,
        ).filter(ClientCompanyLoan.branch_id == branch_id)

    companies = company_query.all()
    branches = branch_query.all()
    loans = loan_query.all()
    payments = payment_query.all()

    employee_scores_by_branch: dict[UUID | None, list[float]] = defaultdict(list)
    staff_company_by_id = {}
    scoped_staff_query = db.query(CompanyStaff.id, CompanyStaff.company_id)
    if company_id:
        scoped_staff_query = scoped_staff_query.filter(CompanyStaff.company_id == company_id)
    if branch_id:
        scoped_staff_query = scoped_staff_query.filter(CompanyStaff.branch_id == branch_id)
    for staff_id, staff_company_id in scoped_staff_query.all():
        staff_company_by_id[staff_id] = staff_company_id

    for employee in employees:
        employee_scores_by_branch[employee.branch_id].append(employee.performance_score)

    loans_by_branch: dict[UUID | None, list[ClientCompanyLoan]] = defaultdict(list)
    loans_by_company: dict[UUID, list[ClientCompanyLoan]] = defaultdict(list)
    for loan in loans:
        loans_by_branch[loan.branch_id].append(loan)
        loans_by_company[loan.company_id].append(loan)

    payments_by_loan: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    payments_by_company: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment in payments:
        if payment.loan_id:
            payments_by_loan[payment.loan_id] += _decimal(payment.amount)
        if payment.company_id:
            payments_by_company[payment.company_id] += _decimal(payment.amount)

    branch_rows: list[BranchPerformanceRead] = []
    for branch in branches:
        branch_loans = loans_by_branch.get(branch.id, [])
        scores = employee_scores_by_branch.get(branch.id, [])
        branch_rows.append(
            BranchPerformanceRead(
                branch_id=branch.id,
                branch_name=branch.name,
                employee_count=len(scores),
                active_loans=sum(1 for loan in branch_loans if loan.status == LoanStatus.ACTIVE),
                overdue_loans=sum(1 for loan in branch_loans if loan.is_overdue),
                loan_principal=sum(
                    (_decimal(loan.principal_amount) for loan in branch_loans),
                    Decimal("0"),
                ),
                payments_received=sum(
                    (payments_by_loan.get(loan.id, Decimal("0")) for loan in branch_loans),
                    Decimal("0"),
                ),
                average_employee_score=(
                    round(sum(scores) / len(scores), 2) if scores else 0
                ),
            )
        )

    company_rows: list[CompanyPerformanceRead] = []
    for company in companies:
        company_loans = loans_by_company.get(company.id, [])
        company_employee_scores = [
            employee.performance_score
            for employee in employees
            if staff_company_by_id.get(employee.staff_id) == company.id
        ]
        employee_average = (
            round(sum(company_employee_scores) / len(company_employee_scores), 2)
            if company_employee_scores
            else 0
        )
        active_loans = sum(
            1 for loan in company_loans if loan.status == LoanStatus.ACTIVE
        )
        overdue_loans = sum(1 for loan in company_loans if loan.is_overdue)
        overdue_rate = (
            overdue_loans / active_loans * 100
            if active_loans
            else 0
        )
        operational_score = round(
            max(
                0,
                min(
                    100,
                    employee_average * 0.55
                    + (100 - overdue_rate) * 0.45,
                ),
            ),
            2,
        )

        company_rows.append(
            CompanyPerformanceRead(
                company_id=company.id,
                company_name=company.name,
                employee_count=len(company_employee_scores),
                branch_count=sum(
                    1 for branch in branches if branch.company_id == company.id
                ),
                active_loans=active_loans,
                overdue_loans=overdue_loans,
                outstanding_balance=sum(
                    (_decimal(loan.balance) for loan in company_loans),
                    Decimal("0"),
                ),
                successful_payments=payments_by_company.get(
                    company.id,
                    Decimal("0"),
                ),
                employee_average_score=employee_average,
                operational_score=operational_score,
            )
        )

    average_employee = (
        round(
            sum(employee.performance_score for employee in employees)
            / len(employees),
            2,
        )
        if employees
        else 0
    )

    return PerformanceOverviewRead(
        scope=(
            "branch"
            if branch_id
            else "company"
            if company_id
            else "platform"
        ),
        employee_count=len(employees),
        branch_count=len(branches),
        company_count=len(companies),
        active_loans=sum(1 for loan in loans if loan.status == LoanStatus.ACTIVE),
        overdue_loans=sum(1 for loan in loans if loan.is_overdue),
        total_outstanding=sum(
            (_decimal(loan.balance) for loan in loans),
            Decimal("0"),
        ),
        successful_payments=sum(
            (_decimal(payment.amount) for payment in payments),
            Decimal("0"),
        ),
        average_employee_score=average_employee,
        employees=employees,
        branches=sorted(
            branch_rows,
            key=lambda item: item.average_employee_score,
            reverse=True,
        ),
        companies=sorted(
            company_rows,
            key=lambda item: item.operational_score,
            reverse=True,
        ),
    )
