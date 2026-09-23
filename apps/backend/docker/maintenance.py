from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database.config.config import settings
from database.session import SessionLocal
from services.call_management_service import delete_expired_recordings
from services.cdas_daily_intelligence import run_daily_cdas_intelligence
from services.maintenance_service import run_maintenance
from services.nightly_service import run_midnight_reconciliation
from services.collection_daily_reporting_service import run_missed_payment_reporting

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("loanhub.maintenance")

_CDAS_DAILY_HOUR = 3
_CDAS_DAILY_MINUTE = 45
_CDAS_DAILY_MAX_PROFILES = 100


def _seconds_until_next_midnight() -> float:
    zone = ZoneInfo(settings.APP_TIMEZONE)
    now = datetime.now(zone)
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=zone)
    return max(1.0, (next_midnight - now).total_seconds())


def _seconds_until_next_collection_report() -> float:
    zone = ZoneInfo(settings.APP_TIMEZONE)
    now = datetime.now(zone)
    target = now.replace(
        hour=max(0, min(23, settings.COLLECTION_DAILY_REPORT_HOUR)),
        minute=max(0, min(59, settings.COLLECTION_DAILY_REPORT_MINUTE)),
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _seconds_until_next_cdas_intelligence() -> float:
    zone = ZoneInfo(settings.APP_TIMEZONE)
    now = datetime.now(zone)
    target = now.replace(
        hour=_CDAS_DAILY_HOUR,
        minute=_CDAS_DAILY_MINUTE,
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def main() -> None:
    interval = max(60, settings.MAINTENANCE_INTERVAL_SECONDS)
    logger.info("Cash-only maintenance worker started; interval=%s; timezone=%s", interval, settings.APP_TIMEZONE)
    last_midnight_date = None
    last_collection_report_date = None
    last_cdas_intelligence_date = None

    while True:
        db = SessionLocal()
        try:
            result = run_maintenance(db)
            logger.info("Maintenance completed: %s", result.to_dict())
        except Exception:
            db.rollback()
            logger.exception("Maintenance run failed")
        finally:
            db.close()

        retention_db = SessionLocal()
        try:
            retention = delete_expired_recordings(retention_db)
            if any(retention.values()):
                logger.info("Call recording retention completed: %s", retention)
        except Exception:
            retention_db.rollback()
            logger.exception("Call recording retention run failed")
        finally:
            retention_db.close()

        zone = ZoneInfo(settings.APP_TIMEZONE)
        local_now = datetime.now(zone)

        if settings.MIDNIGHT_REPORTS_ENABLED and last_midnight_date != local_now.date():
            if local_now.hour == 0 or last_midnight_date is None:
                nightly_db = SessionLocal()
                try:
                    outcome = run_midnight_reconciliation(nightly_db, local_now.date())
                    logger.info("Nightly report outcome: %s", outcome)
                    last_midnight_date = local_now.date()
                except Exception:
                    nightly_db.rollback()
                    logger.exception("Nightly reconciliation/report generation failed")
                finally:
                    nightly_db.close()

        collection_due = (
            local_now.hour,
            local_now.minute,
        ) >= (
            max(0, min(23, settings.COLLECTION_DAILY_REPORT_HOUR)),
            max(0, min(59, settings.COLLECTION_DAILY_REPORT_MINUTE)),
        )
        if (
            settings.COLLECTION_DAILY_REPORT_ENABLED
            and last_collection_report_date != local_now.date()
            and collection_due
        ):
            collection_db = SessionLocal()
            try:
                outcome = run_missed_payment_reporting(collection_db, local_date=local_now.date())
                logger.info("Collection report outcome: %s", outcome)
                last_collection_report_date = local_now.date()
            except Exception:
                collection_db.rollback()
                logger.exception("Daily missed-payment report generation failed")
            finally:
                collection_db.close()

        cdas_due = (local_now.hour, local_now.minute) >= (_CDAS_DAILY_HOUR, _CDAS_DAILY_MINUTE)
        if last_cdas_intelligence_date != local_now.date() and cdas_due:
            # Mark the date before execution so a partial provider outage cannot
            # consume the daily CDAS allowance repeatedly every maintenance tick.
            last_cdas_intelligence_date = local_now.date()
            cdas_db = SessionLocal()
            try:
                outcome = asyncio.run(
                    run_daily_cdas_intelligence(
                        cdas_db,
                        local_date=local_now.date(),
                        max_profiles=_CDAS_DAILY_MAX_PROFILES,
                    )
                )
                logger.info("Daily CDAS intelligence outcome: %s", outcome)
            except Exception:
                cdas_db.rollback()
                logger.exception("Daily CDAS intelligence run failed")
            finally:
                cdas_db.close()

        time.sleep(min(
            interval,
            _seconds_until_next_midnight(),
            _seconds_until_next_collection_report(),
            _seconds_until_next_cdas_intelligence(),
        ))


if __name__ == "__main__":
    main()
