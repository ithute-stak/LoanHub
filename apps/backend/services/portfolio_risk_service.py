from __future__ import annotations

import csv
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.collection_automation import CollectionWorkItem
from database.models.company import LoanCompany
from database.models.enums import LoanStatus
from database.models.lending_operations import CollectionCase
from database.models.loan_product import LoanProduct
from database.models.portfolio_risk import PortfolioRiskRun, PortfolioRiskSnapshot
from database.models.professional_lending import DirectLoanApplication
from database.models.repayment import RepaymentInstallment


MONEY = Decimal("0.01")
ACTIVE_STATUSES = {LoanStatus.APPROVED, LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
BUCKET_ORDER = {
    "current": 0,
    "1-7": 1,
    "8-30": 2,
    "31-60": 3,
    "61-90": 4,
    "90+": 5,
}


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def safe_percent(numerator: Decimal | float | int, denominator: Decimal | float | int) -> float:
    denominator_value = Decimal(str(denominator or 0))
    if denominator_value == 0:
        return 0.0
    return round(float(Decimal(str(numerator or 0)) / denominator_value * Decimal("100")), 2)


def dpd_bucket(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 7:
        return "1-7"
    if days <= 30:
        return "8-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def _loan_dpd(installments: list[RepaymentInstallment], as_of: date) -> tuple[int, Decimal]:
    overdue: list[RepaymentInstallment] = [
        row for row in installments
        if not row.is_superseded
        and row.due_date < as_of
        and money(row.paid_amount) < money(row.total_due)
    ]
    if not overdue:
        return 0, Decimal("0.00")
    earliest = min(row.due_date for row in overdue)
    overdue_amount = sum(
        (max(money(row.total_due) - money(row.paid_amount), Decimal("0.00")) for row in overdue),
        Decimal("0.00"),
    )
    return max((as_of - earliest).days, 0), money(overdue_amount)


def _first_payment_default(installments: list[RepaymentInstallment], as_of: date) -> bool:
    active = sorted((row for row in installments if not row.is_superseded), key=lambda row: row.installment_number)
    if not active:
        return False
    first = active[0]
    if first.due_date >= as_of:
        return False
    if first.paid_at:
        return first.paid_at.date() > first.due_date
    return money(first.paid_amount) < money(first.total_due)


def _collection_channel(loan: ClientCompanyLoan) -> str:
    if loan.cdas_collection_enabled:
        return "cdas"
    if loan.borrower and loan.borrower.employer_group_id:
        return "employer_or_direct"
    return "direct"


def _origination_date(loan: ClientCompanyLoan) -> date | None:
    value = loan.disbursed_at or loan.approved_at or loan.created_at
    return value.date() if value else None


def _month_start(value: date | None) -> date | None:
    return value.replace(day=1) if value else None


def _load_portfolio_context(db: Session, company_id: UUID) -> tuple[list[ClientCompanyLoan], dict[UUID, list[RepaymentInstallment]], dict[UUID, UUID | None], dict[UUID, str], dict[UUID, CollectionCase]]:
    loans = (
        db.query(ClientCompanyLoan)
        .options(
            joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.employer_group),
            joinedload(ClientCompanyLoan.branch),
        )
        .filter(ClientCompanyLoan.company_id == company_id)
        .all()
    )
    loan_ids = [row.id for row in loans]
    installments_by_loan: dict[UUID, list[RepaymentInstallment]] = defaultdict(list)
    if loan_ids:
        installments = db.query(RepaymentInstallment).filter(RepaymentInstallment.loan_id.in_(loan_ids)).all()
        for row in installments:
            installments_by_loan[row.loan_id].append(row)

    product_id_by_loan: dict[UUID, UUID | None] = {}
    product_labels: dict[UUID, str] = {}
    direct_ids = [row.direct_application_id for row in loans if row.direct_application_id]
    if direct_ids:
        applications = db.query(DirectLoanApplication).filter(DirectLoanApplication.id.in_(direct_ids)).all()
        by_application = {row.id: row for row in applications}
        product_ids = {row.product_id for row in applications if row.product_id}
        if product_ids:
            products = db.query(LoanProduct).filter(LoanProduct.id.in_(product_ids)).all()
            product_labels = {row.id: row.name for row in products}
        for loan in loans:
            application = by_application.get(loan.direct_application_id)
            product_id_by_loan[loan.id] = application.product_id if application else None

    cases = db.query(CollectionCase).filter(CollectionCase.company_id == company_id).all()
    latest_case_by_loan: dict[UUID, CollectionCase] = {}
    for case in sorted(cases, key=lambda row: row.updated_at or row.created_at, reverse=True):
        latest_case_by_loan.setdefault(case.loan_id, case)
    return loans, installments_by_loan, product_id_by_loan, product_labels, latest_case_by_loan


def _snapshot_values(
    loan: ClientCompanyLoan,
    installments: list[RepaymentInstallment],
    *,
    as_of: date,
    product_id: UUID | None,
    product_label: str | None,
    collection_case: CollectionCase | None,
) -> dict[str, Any]:
    dpd, overdue_amount = _loan_dpd(installments, as_of)
    origin = _origination_date(loan)
    borrower = loan.borrower
    employer_group = borrower.employer_group if borrower else None
    branch = loan.branch
    written_off = bool(collection_case and collection_case.status == "written_off")
    return {
        "company_id": loan.company_id,
        "branch_id": loan.branch_id,
        "loan_id": loan.id,
        "borrower_id": loan.borrower_id,
        "employer_group_id": borrower.employer_group_id if borrower else None,
        "product_id": product_id,
        "snapshot_date": as_of,
        "origination_month": _month_start(origin),
        "days_past_due": dpd,
        "delinquency_bucket": dpd_bucket(dpd),
        "outstanding_balance": max(money(loan.balance), Decimal("0.00")),
        "overdue_amount": overdue_amount,
        "principal_amount": money(loan.principal_amount),
        "installment_amount": money(loan.installment_amount),
        "loan_status": getattr(loan.status, "value", str(loan.status)),
        "origination_channel": loan.origination_channel or "unknown",
        "collection_channel": _collection_channel(loan),
        "product_label": product_label or f"{loan.calculation_method or 'Unmapped'} lending",
        "employer_label": employer_group.name if employer_group else (borrower.employer_name if borrower and borrower.employer_name else "No employer group"),
        "branch_label": branch.name if branch else "Unassigned branch",
        "is_top_up": bool(loan.is_top_up),
        "first_payment_default": _first_payment_default(installments, as_of),
        "is_written_off": written_off,
        "cdas_collection_enabled": bool(loan.cdas_collection_enabled),
        "generated_at": datetime.now(timezone.utc),
        "evidence_snapshot": {
            "folio_number": loan.folio_number,
            "loan_reference": loan.loan_reference,
            "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
            "first_payment_due": loan.first_payment_due.isoformat() if loan.first_payment_due else None,
            "calculation_method": loan.calculation_method,
            "collection_case_status": collection_case.status if collection_case else None,
        },
    }


def generate_snapshot(
    db: Session,
    *,
    company_id: UUID,
    snapshot_date: date,
    triggered_by_user_id: UUID | None = None,
) -> PortfolioRiskRun:
    loans, installments_by_loan, product_id_by_loan, product_labels, cases = _load_portfolio_context(db, company_id)
    existing = {
        row.loan_id: row
        for row in db.query(PortfolioRiskSnapshot).filter(
            PortfolioRiskSnapshot.company_id == company_id,
            PortfolioRiskSnapshot.snapshot_date == snapshot_date,
        ).all()
    }
    active_exposure = Decimal("0.00")
    par30 = Decimal("0.00")
    active_count = 0
    for loan in loans:
        values = _snapshot_values(
            loan,
            installments_by_loan.get(loan.id, []),
            as_of=snapshot_date,
            product_id=product_id_by_loan.get(loan.id),
            product_label=product_labels.get(product_id_by_loan.get(loan.id)),
            collection_case=cases.get(loan.id),
        )
        row = existing.get(loan.id)
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            row = PortfolioRiskSnapshot(**values)
            db.add(row)
        if loan.status in ACTIVE_STATUSES and values["outstanding_balance"] > 0:
            active_count += 1
            active_exposure += values["outstanding_balance"]
            if values["days_past_due"] >= 30:
                par30 += values["outstanding_balance"]

    run = db.query(PortfolioRiskRun).filter(
        PortfolioRiskRun.company_id == company_id,
        PortfolioRiskRun.snapshot_date == snapshot_date,
        PortfolioRiskRun.branch_scope_key == "ALL",
    ).first()
    summary = {
        "active_loan_count": active_count,
        "par_30_percent": safe_percent(par30, active_exposure),
        "snapshot_method": "live installment state at snapshot time",
    }
    if not run:
        run = PortfolioRiskRun(
            company_id=company_id,
            branch_id=None,
            branch_scope_key="ALL",
            snapshot_date=snapshot_date,
            run_reference=f"RISK-{snapshot_date:%Y%m%d}-{secrets.token_hex(4).upper()}",
            triggered_by_user_id=triggered_by_user_id,
        )
        db.add(run)
    run.loan_count = len(loans)
    run.active_exposure = money(active_exposure)
    run.par_30_amount = money(par30)
    run.summary = summary
    run.generated_at = datetime.now(timezone.utc)
    if triggered_by_user_id:
        run.triggered_by_user_id = triggered_by_user_id
    db.commit()
    db.refresh(run)
    return run


def ensure_today_snapshot(db: Session, company_id: UUID, today: date) -> PortfolioRiskRun:
    run = db.query(PortfolioRiskRun).filter(
        PortfolioRiskRun.company_id == company_id,
        PortfolioRiskRun.snapshot_date == today,
        PortfolioRiskRun.branch_scope_key == "ALL",
    ).first()
    if run:
        return run
    return generate_snapshot(db, company_id=company_id, snapshot_date=today)


def _active_rows(rows: list[PortfolioRiskSnapshot]) -> list[PortfolioRiskSnapshot]:
    active_names = {item.value for item in ACTIVE_STATUSES}
    return [row for row in rows if row.loan_status in active_names and money(row.outstanding_balance) > 0 and not row.is_written_off]


def _par_metrics(rows: list[PortfolioRiskSnapshot]) -> dict[str, Any]:
    active = _active_rows(rows)
    exposure = sum((money(row.outstanding_balance) for row in active), Decimal("0.00"))
    result: dict[str, Any] = {"active_exposure": float(money(exposure)), "active_loans": len(active)}
    for threshold in (1, 7, 30, 60, 90):
        amount = sum((money(row.outstanding_balance) for row in active if row.days_past_due >= threshold), Decimal("0.00"))
        result[f"par_{threshold}_amount"] = float(money(amount))
        result[f"par_{threshold}"] = safe_percent(amount, exposure)
    return result


def _group_risk(rows: list[PortfolioRiskSnapshot], label_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[PortfolioRiskSnapshot]] = defaultdict(list)
    for row in _active_rows(rows):
        grouped[str(getattr(row, label_field) or "Unknown")].append(row)
    total = sum((money(row.outstanding_balance) for row in _active_rows(rows)), Decimal("0.00"))
    result = []
    for label, group in grouped.items():
        exposure = sum((money(row.outstanding_balance) for row in group), Decimal("0.00"))
        par30 = sum((money(row.outstanding_balance) for row in group if row.days_past_due >= 30), Decimal("0.00"))
        fpd_eligible = [row for row in group if row.evidence_snapshot.get("first_payment_due")]
        result.append({
            "label": label,
            "loan_count": len(group),
            "exposure": float(money(exposure)),
            "share_percent": safe_percent(exposure, total),
            "par_30": safe_percent(par30, exposure),
            "fpd_rate": safe_percent(sum(row.first_payment_default for row in fpd_eligible), len(fpd_eligible)),
        })
    return sorted(result, key=lambda row: (-row["exposure"], row["label"]))


def _concentration(rows: list[PortfolioRiskSnapshot], label_field: str) -> dict[str, Any]:
    groups = _group_risk(rows, label_field)
    hhi = round(sum((row["share_percent"] / 100) ** 2 for row in groups) * 10000, 2)
    return {
        "hhi": hhi,
        "top_share_percent": groups[0]["share_percent"] if groups else 0.0,
        "group_count": len(groups),
        "groups": groups,
    }


def _vintages(rows: list[PortfolioRiskSnapshot]) -> list[dict[str, Any]]:
    grouped: dict[date, list[PortfolioRiskSnapshot]] = defaultdict(list)
    for row in rows:
        if row.origination_month:
            grouped[row.origination_month].append(row)
    result = []
    for month, group in grouped.items():
        originated = sum((money(row.principal_amount) for row in group), Decimal("0.00"))
        outstanding = sum((money(row.outstanding_balance) for row in group if not row.is_written_off), Decimal("0.00"))
        par30 = sum((money(row.outstanding_balance) for row in group if row.days_past_due >= 30 and not row.is_written_off), Decimal("0.00"))
        eligible = [row for row in group if row.evidence_snapshot.get("first_payment_due")]
        result.append({
            "vintage": month.isoformat()[:7],
            "loan_count": len(group),
            "originated_principal": float(money(originated)),
            "outstanding_balance": float(money(outstanding)),
            "par_30": safe_percent(par30, outstanding),
            "fpd_rate": safe_percent(sum(row.first_payment_default for row in eligible), len(eligible)),
            "write_off_count": sum(row.is_written_off for row in group),
            "top_up_count": sum(row.is_top_up for row in group),
        })
    return sorted(result, key=lambda row: row["vintage"], reverse=True)[:18]


def _top_up_performance(rows: list[PortfolioRiskSnapshot]) -> list[dict[str, Any]]:
    output = []
    for is_top_up, label in ((False, "New / non-top-up"), (True, "Top-up")):
        group = [row for row in rows if row.is_top_up is is_top_up]
        active = _active_rows(group)
        exposure = sum((money(row.outstanding_balance) for row in active), Decimal("0.00"))
        par30 = sum((money(row.outstanding_balance) for row in active if row.days_past_due >= 30), Decimal("0.00"))
        eligible = [row for row in group if row.evidence_snapshot.get("first_payment_due")]
        output.append({
            "label": label,
            "loan_count": len(group),
            "active_exposure": float(money(exposure)),
            "par_30": safe_percent(par30, exposure),
            "fpd_rate": safe_percent(sum(row.first_payment_default for row in eligible), len(eligible)),
            "write_off_count": sum(row.is_written_off for row in group),
        })
    return output


def _transitions(db: Session, company_id: UUID, current_rows: list[PortfolioRiskSnapshot], current_date: date, branch_id: UUID | None) -> dict[str, Any]:
    available_dates_query = db.query(PortfolioRiskSnapshot.snapshot_date).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date < current_date,
    )
    if branch_id:
        available_dates_query = available_dates_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    dates = sorted({row[0] for row in available_dates_query.distinct().all()})
    if not dates:
        return {"available": False, "message": "A second portfolio snapshot is required before roll and cure rates can be measured.", "matrix": []}
    target = current_date - timedelta(days=28)
    older = [value for value in dates if value <= target]
    previous_date = max(older) if older else max(dates)
    previous_query = db.query(PortfolioRiskSnapshot).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date == previous_date,
    )
    if branch_id:
        previous_query = previous_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    previous_rows = previous_query.all()
    previous = {row.loan_id: row for row in previous_rows}
    current = {row.loan_id: row for row in current_rows}
    matrix: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"loan_count": 0, "exposure": Decimal("0.00")})
    delinquent_previous = cured = rolled_forward = 0
    for loan_id, old in previous.items():
        new = current.get(loan_id)
        old_bucket = old.delinquency_bucket
        new_bucket = new.delinquency_bucket if new else "current"
        key = (old_bucket, new_bucket)
        matrix[key]["loan_count"] += 1
        matrix[key]["exposure"] += money(old.outstanding_balance)
        if old.days_past_due > 0:
            delinquent_previous += 1
            if not new or new.days_past_due == 0 or new.loan_status == LoanStatus.COMPLETED.value:
                cured += 1
        if new and BUCKET_ORDER.get(new_bucket, 0) > BUCKET_ORDER.get(old_bucket, 0):
            rolled_forward += 1
    serialized = [
        {
            "from_bucket": source,
            "to_bucket": destination,
            "loan_count": values["loan_count"],
            "exposure": float(money(values["exposure"])),
        }
        for (source, destination), values in sorted(matrix.items(), key=lambda item: (BUCKET_ORDER.get(item[0][0], 99), BUCKET_ORDER.get(item[0][1], 99)))
    ]
    return {
        "available": True,
        "previous_snapshot_date": previous_date.isoformat(),
        "current_snapshot_date": current_date.isoformat(),
        "interval_days": (current_date - previous_date).days,
        "cure_rate": safe_percent(cured, delinquent_previous),
        "roll_forward_rate": safe_percent(rolled_forward, len(previous_rows)),
        "matrix": serialized,
    }


def _projected_cash_flow(db: Session, company_id: UUID, as_of: date, branch_id: UUID | None) -> list[dict[str, Any]]:
    end_date = as_of + timedelta(days=184)
    query = (
        db.query(RepaymentInstallment, ClientCompanyLoan)
        .join(ClientCompanyLoan, ClientCompanyLoan.id == RepaymentInstallment.loan_id)
        .filter(
            ClientCompanyLoan.company_id == company_id,
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.due_date >= as_of,
            RepaymentInstallment.due_date <= end_date,
        )
    )
    if branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == branch_id)
    monthly: dict[str, dict[str, Decimal | int]] = defaultdict(lambda: {"scheduled": Decimal("0.00"), "cdas": Decimal("0.00"), "loan_count": 0})
    loan_ids: dict[str, set[UUID]] = defaultdict(set)
    for installment, loan in query.all():
        remaining = max(money(installment.total_due) - money(installment.paid_amount), Decimal("0.00"))
        key = installment.due_date.isoformat()[:7]
        monthly[key]["scheduled"] += remaining
        if loan.cdas_collection_enabled:
            monthly[key]["cdas"] += remaining
        loan_ids[key].add(loan.id)
    return [
        {
            "month": key,
            "scheduled_collections": float(money(values["scheduled"])),
            "cdas_scheduled": float(money(values["cdas"])),
            "non_cdas_scheduled": float(money(values["scheduled"] - values["cdas"])),
            "loan_count": len(loan_ids[key]),
        }
        for key, values in sorted(monthly.items())
    ]


def build_overview(db: Session, *, company_id: UUID, branch_id: UUID | None, as_of: date) -> dict[str, Any]:
    ensure_today_snapshot(db, company_id, as_of)
    query = db.query(PortfolioRiskSnapshot).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date == as_of,
    )
    if branch_id:
        query = query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    rows = query.all()
    par = _par_metrics(rows)
    fpd_eligible = [row for row in rows if row.evidence_snapshot.get("first_payment_due") and row.origination_month and row.origination_month <= as_of]
    written_off = [row for row in rows if row.is_written_off]
    write_off_amount = sum((money(row.outstanding_balance) for row in written_off), Decimal("0.00"))
    active_exposure = Decimal(str(par["active_exposure"]))

    open_recovery_query = db.query(CollectionWorkItem).filter(
        CollectionWorkItem.company_id == company_id,
        CollectionWorkItem.status.in_(["open", "in_progress"]),
    )
    if branch_id:
        open_recovery_query = open_recovery_query.filter(CollectionWorkItem.branch_id == branch_id)

    return {
        "as_of": as_of.isoformat(),
        "summary": {
            **par,
            "fpd_rate": safe_percent(sum(row.first_payment_default for row in fpd_eligible), len(fpd_eligible)),
            "fpd_loans": sum(row.first_payment_default for row in fpd_eligible),
            "write_off_count": len(written_off),
            "write_off_amount": float(money(write_off_amount)),
            "write_off_rate": safe_percent(write_off_amount, active_exposure + write_off_amount),
            "top_up_exposure": float(money(sum((money(row.outstanding_balance) for row in _active_rows(rows) if row.is_top_up), Decimal("0.00")))),
            "cdas_exposure": float(money(sum((money(row.outstanding_balance) for row in _active_rows(rows) if row.cdas_collection_enabled), Decimal("0.00")))),
            "open_recovery_work_items": open_recovery_query.count(),
        },
        "delinquency_buckets": [
            {
                "bucket": bucket,
                "loan_count": sum(row.delinquency_bucket == bucket for row in _active_rows(rows)),
                "exposure": float(money(sum((money(row.outstanding_balance) for row in _active_rows(rows) if row.delinquency_bucket == bucket), Decimal("0.00")))),
            }
            for bucket in BUCKET_ORDER
        ],
        "roll_and_cure": _transitions(db, company_id, rows, as_of, branch_id),
        "vintages": _vintages(rows),
        "top_up_performance": _top_up_performance(rows),
        "branch_risk": _group_risk(rows, "branch_label"),
        "product_risk": _group_risk(rows, "product_label"),
        "employer_risk": _group_risk(rows, "employer_label"),
        "concentration": {
            "branch": _concentration(rows, "branch_label"),
            "product": _concentration(rows, "product_label"),
            "employer": _concentration(rows, "employer_label"),
        },
        "projected_cash_flow": _projected_cash_flow(db, company_id, as_of, branch_id),
        "methodology": {
            "par": "Outstanding active exposure with days-past-due at or above each threshold divided by active exposure.",
            "first_payment_default": "First scheduled installment was unpaid after its due date or was only fully paid after its due date.",
            "roll_and_cure": "Measured from stored daily loan-level snapshots; no transition rate is invented before two snapshots exist.",
            "write_off": "Collection cases explicitly marked written_off; LoanHub does not infer a write-off from delinquency alone.",
            "projected_cash_flow": "Remaining unpaid scheduled installments due during the next six months; this is contractual cash flow, not a guarantee of collection.",
        },
    }


def risk_history(db: Session, *, company_id: UUID, branch_id: UUID | None, limit: int = 120) -> list[dict[str, Any]]:
    dates_query = db.query(PortfolioRiskSnapshot.snapshot_date).filter(PortfolioRiskSnapshot.company_id == company_id)
    if branch_id:
        dates_query = dates_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    dates = sorted({row[0] for row in dates_query.distinct().all()}, reverse=True)[:limit]
    result = []
    for snapshot_date in reversed(dates):
        query = db.query(PortfolioRiskSnapshot).filter(
            PortfolioRiskSnapshot.company_id == company_id,
            PortfolioRiskSnapshot.snapshot_date == snapshot_date,
        )
        if branch_id:
            query = query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
        rows = query.all()
        par = _par_metrics(rows)
        result.append({
            "date": snapshot_date.isoformat(),
            "active_exposure": par["active_exposure"],
            "par_1": par["par_1"],
            "par_7": par["par_7"],
            "par_30": par["par_30"],
            "par_60": par["par_60"],
            "par_90": par["par_90"],
        })
    return result


def overview_csv(overview: dict[str, Any]) -> str:
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["LoanHub Portfolio Risk Intelligence", overview["as_of"]])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    for key, value in overview["summary"].items():
        writer.writerow([key, value])
    writer.writerow([])
    writer.writerow(["Delinquency bucket", "Loan count", "Exposure"])
    for row in overview["delinquency_buckets"]:
        writer.writerow([row["bucket"], row["loan_count"], row["exposure"]])
    writer.writerow([])
    writer.writerow(["Vintage", "Loans", "Originated principal", "Outstanding", "PAR 30 %", "FPD %", "Write-offs", "Top-ups"])
    for row in overview["vintages"]:
        writer.writerow([row["vintage"], row["loan_count"], row["originated_principal"], row["outstanding_balance"], row["par_30"], row["fpd_rate"], row["write_off_count"], row["top_up_count"]])
    writer.writerow([])
    writer.writerow(["Projected month", "Scheduled collections", "CDAS scheduled", "Non-CDAS scheduled", "Loans"])
    for row in overview["projected_cash_flow"]:
        writer.writerow([row["month"], row["scheduled_collections"], row["cdas_scheduled"], row["non_cdas_scheduled"], row["loan_count"]])
    return stream.getvalue()


def run_scheduled_portfolio_risk(db: Session, local_date: date) -> dict[str, Any]:
    company_ids = [row[0] for row in db.query(LoanCompany.id).filter(LoanCompany.is_active.is_(True)).all()]
    completed = []
    failures = []
    for company_id in company_ids:
        try:
            run = generate_snapshot(db, company_id=company_id, snapshot_date=local_date)
            completed.append({"company_id": str(company_id), "run_reference": run.run_reference, "loan_count": run.loan_count})
        except Exception as exc:
            db.rollback()
            failures.append({"company_id": str(company_id), "error": str(exc)})
    return {"companies_checked": len(company_ids), "completed": completed, "failures": failures}
