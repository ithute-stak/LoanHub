"""Fail-closed reservation helpers for individual CDAS affordability.

A persisted reservation is committed BEFORE any provider contact. Its
existence prevents a second provider request using the same key, even if a
worker or browser dies. This is not a guarantee of provider-side idempotency.
"""
import hashlib
import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from database.models.cdas_affordability_attempt import CdasAffordabilityAttempt


def affordability_request_fingerprint(*, company_id, borrower_id, employee_number, installment, consent_evidence_reference=""):
    canonical = {
        "company_id": str(company_id),
        "borrower_id": str(borrower_id),
        "employee_number": employee_number.strip().casefold(),
        "installment": str(Decimal(str(installment)).quantize(Decimal("0.01"))),
        "consent_evidence_reference": consent_evidence_reference.strip(),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def find_attempt(db, *, company_id, idempotency_key):
    return db.query(CdasAffordabilityAttempt).filter(
        CdasAffordabilityAttempt.company_id == company_id,
        CdasAffordabilityAttempt.idempotency_key == idempotency_key,
    ).first()


def reserve_affordability_attempt(db, *, company_id, actor_user_id, borrower_id,
                                  employee_number, installment, idempotency_key, consent_evidence_reference=""):
    fingerprint = affordability_request_fingerprint(
        company_id=company_id, borrower_id=borrower_id,
        employee_number=employee_number, installment=installment,
        consent_evidence_reference=consent_evidence_reference,
    )
    prior = find_attempt(db, company_id=company_id, idempotency_key=idempotency_key)
    if prior:
        if prior.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Idempotency key belongs to another assessment")
        return prior, False

    unresolved = db.query(CdasAffordabilityAttempt).filter(
        CdasAffordabilityAttempt.company_id == company_id,
        CdasAffordabilityAttempt.request_fingerprint == fingerprint,
        CdasAffordabilityAttempt.state.in_(("reserved", "unknown")),
    ).first()
    if unresolved is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Unresolved matching CDAS assessment already exists; do not issue another provider request",
                **safe_attempt_status(unresolved),
            },
        )

    attempt = CdasAffordabilityAttempt(
        company_id=company_id, actor_user_id=actor_user_id,
        borrower_id=borrower_id, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint, state="reserved",
    )
    db.add(attempt)
    try:
        db.commit()
        db.refresh(attempt)
        return attempt, True
    except IntegrityError as exc:
        db.rollback()
        prior = find_attempt(db, company_id=company_id, idempotency_key=idempotency_key)
        if prior:
            if prior.request_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency key belongs to another assessment") from exc
            return prior, False
        unresolved = db.query(CdasAffordabilityAttempt).filter(
            CdasAffordabilityAttempt.company_id == company_id,
            CdasAffordabilityAttempt.request_fingerprint == fingerprint,
            CdasAffordabilityAttempt.state.in_(("reserved", "unknown")),
        ).first()
        if unresolved is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Concurrent unresolved assessment prevents another CDAS call",
                    **safe_attempt_status(unresolved),
                },
            ) from exc
        raise


def safe_attempt_status(attempt):
    return {
        "attempt_id": str(attempt.id),
        "status": attempt.state,
        "record_id": str(attempt.assessment_record_id) if attempt.assessment_record_id else None,
        "requires_manual_review": attempt.state != "completed",
        "may_retry_provider_request": False,
    }
