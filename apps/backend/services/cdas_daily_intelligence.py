from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingOpportunity
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from database.models.lending_operations import CDASPayrollProfile
from integrations.cdas import CdasError
from services.cdas_borrower_intelligence import build_borrower_loan_intelligence
from services.cdas_config_service import get_company_cdas_client, get_configuration


_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _deduction_amount(row: dict[str, Any]) -> Decimal:
    for key in ("DeductionAmount", "deductionAmount", "deduction_amount", "Amount", "amount"):
        if key in row:
            return max(_money(row.get(key)), Decimal("0.00"))
    return Decimal("0.00")


def classify_daily_collection_action(*, outstanding: object, affordability: object) -> str:
    balance = max(_money(outstanding), Decimal("0.00"))
    available = max(_money(affordability), Decimal("0.00"))
    if balance <= 0:
        return "NO_OUTSTANDING_BALANCE"
    if available <= 0:
        return "MONITOR_NO_CAPACITY"
    return "READY_FOR_COLLECTION_REVIEW"


def _eligible_profiles(db: Session, *, limit: int) -> list[CDASPayrollProfile]:
    rows = (
        db.query(CDASPayrollProfile)
        .join(
            ClientCompanyLoan,
            (ClientCompanyLoan.company_id == CDASPayrollProfile.company_id)
            & (ClientCompanyLoan.borrower_id == CDASPayrollProfile.borrower_id),
        )
        .filter(
            CDASPayrollProfile.verified.is_(True),
            ClientCompanyLoan.status.in_(_ELIGIBLE_LOAN_STATUSES),
            ClientCompanyLoan.balance > 0,
        )
        .order_by(CDASPayrollProfile.company_id, CDASPayrollProfile.verified_at.asc().nullsfirst())
        .distinct()
        .limit(max(0, int(limit)))
        .all()
    )
    return rows


def _get_or_create_opportunity(db: Session, *, profile: CDASPayrollProfile) -> CdasBookingOpportunity:
    client_reference = f"borrower:{profile.borrower_id}"
    row = (
        db.query(CdasBookingOpportunity)
        .filter(
            CdasBookingOpportunity.company_id == profile.company_id,
            CdasBookingOpportunity.client_reference == client_reference,
        )
        .one_or_none()
    )
    if row is None:
        row = CdasBookingOpportunity(
            company_id=profile.company_id,
            client_reference=client_reference,
            status="monitoring",
            pipeline_stage="identified",
        )
        db.add(row)
    return row


def _upsert_monitoring_opportunity(
    db: Session,
    *,
    profile: CDASPayrollProfile,
    affordability: float,
    deductions: list[dict[str, Any]],
    loan_intelligence: dict[str, Any],
    local_date: date,
    environment: str,
) -> CdasBookingOpportunity:
    row = _get_or_create_opportunity(db, profile=profile)

    proposal = loan_intelligence.get("collection_proposal") or {}
    action = classify_daily_collection_action(
        outstanding=loan_intelligence.get("total_outstanding"),
        affordability=affordability,
    )
    total_deductions = sum((_deduction_amount(item) for item in deductions), Decimal("0.00"))

    row.status = "monitoring"
    if action == "READY_FOR_COLLECTION_REVIEW":
        row.pipeline_stage = "ready_to_book"
        row.pipeline_updated_at = datetime.now(timezone.utc)
    row.total_monthly_deductions = total_deductions
    row.analysis_snapshot = {
        "source": "CDAS_DAILY_INTELLIGENCE",
        "environment": environment,
        "local_date": local_date.isoformat(),
        "last_check_date": local_date.isoformat(),
        "last_check_status": "success",
        "identity_policy": "EXACT_NATIONAL_ID_VERIFIED_PROFILE_ONLY",
        "borrower_id": str(profile.borrower_id),
        "employee_no": profile.employee_number,
        "available_affordability": float(_money(affordability)),
        "returned_deduction_count": len(deductions),
        "total_returned_monthly_deductions": float(total_deductions),
        "loanhub": loan_intelligence,
        "recommended_action": action,
        "suggested_monthly_deduction": proposal.get("suggested_monthly_deduction", 0),
        "estimated_collection_months": proposal.get("estimated_collection_months"),
        "provider_write_performed": False,
        "note": "Daily monitoring only. Any CDAS registration/modification/approval remains behind the official loan-linked lifecycle and borrower-consent controls.",
    }
    return row


def _record_failed_check(
    db: Session,
    *,
    profile: CDASPayrollProfile,
    local_date: date,
    error: Exception,
    environment: str,
) -> CdasBookingOpportunity:
    """Persist sanitized overnight check health without destroying the last good result."""
    row = _get_or_create_opportunity(db, profile=profile)
    snapshot = dict(row.analysis_snapshot or {})
    snapshot.setdefault("source", "CDAS_DAILY_INTELLIGENCE")
    snapshot["environment"] = environment
    snapshot.setdefault("identity_policy", "EXACT_NATIONAL_ID_VERIFIED_PROFILE_ONLY")
    snapshot.setdefault("borrower_id", str(profile.borrower_id))
    snapshot.setdefault("employee_no", profile.employee_number)
    snapshot["last_check_date"] = local_date.isoformat()
    snapshot["last_check_status"] = "failed"
    snapshot["last_check_error"] = {
        "provider": "CDAS",
        "status_code": getattr(error, "status_code", None),
        "message": str(getattr(error, "message", None) or "CDAS daily check failed")[:300],
    }
    snapshot["retry_policy"] = "NEXT_SCHEDULED_DAILY_RUN"
    snapshot["provider_write_performed"] = False
    row.analysis_snapshot = snapshot
    row.status = "monitoring"
    return row


async def run_daily_cdas_intelligence(
    db: Session,
    *,
    local_date: date,
    max_profiles: int = 100,
) -> dict[str, Any]:
    """Refresh CDAS capacity for verified borrowers with existing LoanHub debt.

    This job is deliberately read-only against CDAS. It never registers, modifies,
    approves or settles a provider deduction automatically. It prepares the
    operational queue using an already verified exact-ID payroll profile.
    """
    profiles = _eligible_profiles(db, limit=max_profiles)
    by_company: dict[UUID, list[CDASPayrollProfile]] = defaultdict(list)
    for profile in profiles:
        by_company[profile.company_id].append(profile)

    checked = 0
    ready = 0
    no_capacity = 0
    failures = 0

    for company_id, company_profiles in by_company.items():
        configuration = get_configuration(db, company_id)
        environment = str(getattr(configuration, "environment", "test") or "test").strip().lower()
        try:
            client = get_company_cdas_client(db, company_id)
        except Exception as exc:
            for profile in company_profiles:
                try:
                    _record_failed_check(
                        db,
                        profile=profile,
                        local_date=local_date,
                        error=exc,
                        environment=environment,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                failures += 1
            continue

        for profile in company_profiles:
            try:
                affordability = await client.affordability(profile.employee_number)
                deductions = await client.all_deductions(profile.employee_number)
                loan_intelligence = build_borrower_loan_intelligence(
                    db,
                    company_id=company_id,
                    borrower_id=profile.borrower_id,
                    affordability=affordability,
                )
                action = classify_daily_collection_action(
                    outstanding=loan_intelligence.get("total_outstanding"),
                    affordability=affordability,
                )
                _upsert_monitoring_opportunity(
                    db,
                    profile=profile,
                    affordability=affordability,
                    deductions=deductions,
                    loan_intelligence=loan_intelligence,
                    local_date=local_date,
                    environment=environment,
                )
                db.commit()
                checked += 1
                if action == "READY_FOR_COLLECTION_REVIEW":
                    ready += 1
                elif action == "MONITOR_NO_CAPACITY":
                    no_capacity += 1
            except CdasError as exc:
                db.rollback()
                try:
                    _record_failed_check(
                        db,
                        profile=profile,
                        local_date=local_date,
                        error=exc,
                        environment=environment,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                failures += 1
            except Exception as exc:
                db.rollback()
                try:
                    _record_failed_check(
                        db,
                        profile=profile,
                        local_date=local_date,
                        error=exc,
                        environment=environment,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                failures += 1

    return {
        "local_date": local_date.isoformat(),
        "eligible_profiles": len(profiles),
        "checked": checked,
        "ready_for_collection_review": ready,
        "monitor_no_capacity": no_capacity,
        "failures": failures,
        "provider_writes": 0,
        "max_profiles": max_profiles,
    }
