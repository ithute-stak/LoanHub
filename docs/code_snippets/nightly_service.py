from __future__ import annotations

import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.branch import CompanyBranch
from database.models.company import LoanCompany
from database.models.enums import CompanyStatus
from database.models.reporting import GeneratedReport
from services.reporting_service import generate_report, period_for_frequency


logger = logging.getLogger('loanhub.nightly')
NIGHTLY_LOCK_ID = 62106420260720


def _frequency_due(local_date: date) -> list[str]:
    values = ['daily']
    if local_date.weekday() == 0:
        values.append('weekly')
    if local_date.day == 1:
        values.append('monthly')
    if local_date.month == 1 and local_date.day == 1:
        values.append('annual')
    return values


def _already_generated(
    db: Session,
    *,
    report_type: str,
    output_format: str,
    scope_type: str,
    company_id,
    branch_id,
    period_start: date,
    period_end: date,
) -> bool:
    query = db.query(GeneratedReport.id).filter(
        GeneratedReport.report_type == report_type,
        GeneratedReport.output_format == output_format,
        GeneratedReport.scope_type == scope_type,
        GeneratedReport.period_start == period_start,
        GeneratedReport.period_end == period_end,
    )
    query = query.filter(
        GeneratedReport.company_id.is_(None)
        if company_id is None
        else GeneratedReport.company_id == company_id,
        GeneratedReport.branch_id.is_(None)
        if branch_id is None
        else GeneratedReport.branch_id == branch_id,
    )
    return query.first() is not None


def run_midnight_reconciliation(db: Session, local_date: date | None = None) -> dict[str, int]:
    if not settings.MIDNIGHT_REPORTS_ENABLED:
        return {'generated': 0, 'skipped': 0}

    current_date = local_date or current_local_date()
    acquired = db.execute(
        text('SELECT pg_try_advisory_xact_lock(:lock_id)'),
        {'lock_id': NIGHTLY_LOCK_ID},
    ).scalar()
    if not acquired:
        return {'generated': 0, 'skipped': 1}

    active_companies = db.query(LoanCompany).filter(
        LoanCompany.status == CompanyStatus.APPROVED,
        LoanCompany.is_active.is_(True),
    ).all()
    active_branches = db.query(CompanyBranch).filter(
        CompanyBranch.is_active.is_(True),
    ).all()

    scopes: list[tuple[str, object, object]] = [('platform', None, None)]
    scopes.extend(('company', company.id, None) for company in active_companies)
    scopes.extend(('branch', branch.company_id, branch.id) for branch in active_branches)

    generated = 0
    skipped = 0
    for frequency in _frequency_due(current_date):
        period_start, period_end = period_for_frequency(frequency, current_date)
        for scope_type, company_id, branch_id in scopes:
            for output_format in settings.midnight_report_formats:
                report_type = f'{frequency}_reconciliation'
                if _already_generated(
                    db,
                    report_type=report_type,
                    output_format=output_format,
                    scope_type=scope_type,
                    company_id=company_id,
                    branch_id=branch_id,
                    period_start=period_start,
                    period_end=period_end,
                ):
                    skipped += 1
                    continue
                generate_report(
                    db,
                    report_type=report_type,
                    output_format=output_format,
                    scope_type=scope_type,
                    period_start=period_start,
                    period_end=period_end,
                    company_id=company_id,
                    branch_id=branch_id,
                    generated_by_user_id=None,
                )
                generated += 1

    db.commit()
    logger.info(
        'Midnight reconciliation finished for %s: generated=%s skipped=%s',
        current_date,
        generated,
        skipped,
    )
    return {'generated': generated, 'skipped': skipped}


def current_local_date() -> date:
    from datetime import datetime
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
