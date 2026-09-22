from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.borrower import Borrower
from database.models.company_operating_system import CompanyOperatingRecord
from database.models.origination import LoanContract, OriginationIntegrationConfiguration
from database.models.user import User
from services.contract_service import refresh_contract_pdf_after_signature, update_contract_status
from services.credential_service import decrypt_credential


MODULE = "contract_signing"
RECORD_TYPE = "email_otp_contract_signature"
OTP_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


@dataclass(frozen=True)
class EmailTransport:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str
    from_name: str
    use_ssl: bool
    starttls: bool


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}{'*' * max(3, len(local) - 1)}@{domain}"


def _borrower_identity(db: Session, contract: LoanContract) -> tuple[str, str]:
    snapshot = contract.terms_snapshot if isinstance(contract.terms_snapshot, dict) else {}
    borrower_snapshot = snapshot.get("borrower") if isinstance(snapshot.get("borrower"), dict) else {}
    name = str((borrower_snapshot or {}).get("name") or "Borrower").strip() or "Borrower"
    email = str((borrower_snapshot or {}).get("email") or "").strip().lower()

    if not email:
        borrower = db.get(Borrower, contract.borrower_id)
        user = db.get(User, borrower.user_id) if borrower else None
        email = str(user.email or "").strip().lower() if user else ""
        if user and user.person and getattr(user.person, "full_name", None):
            name = str(user.person.full_name).strip() or name

    if not email or "@" not in email:
        raise HTTPException(
            status_code=409,
            detail="The borrower must have a valid email address before Email + OTP signing can be used.",
        )
    return name, email


def _email_configuration(db: Session, company_id: Any) -> EmailTransport | None:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == "email",
        )
        .one_or_none()
    )
    configuration = row.configuration if row and isinstance(row.configuration, dict) else {}

    host = str(
        configuration.get("smtp_host")
        or os.getenv("CONTRACT_EMAIL_SMTP_HOST")
        or ""
    ).strip()
    port_text = configuration.get("smtp_port") or os.getenv("CONTRACT_EMAIL_SMTP_PORT") or "587"
    try:
        port = int(port_text)
    except (TypeError, ValueError):
        port = 587

    username = str(
        configuration.get("smtp_username")
        or os.getenv("CONTRACT_EMAIL_SMTP_USERNAME")
        or ""
    ).strip() or None
    password = os.getenv("CONTRACT_EMAIL_SMTP_PASSWORD") or None
    if row and row.encrypted_credentials:
        try:
            password = decrypt_credential(row.encrypted_credentials)
        except RuntimeError:
            password = None

    from_email = str(
        configuration.get("from_email")
        or os.getenv("CONTRACT_EMAIL_FROM")
        or username
        or ""
    ).strip()
    from_name = str(
        configuration.get("from_name")
        or os.getenv("CONTRACT_EMAIL_FROM_NAME")
        or "LoanHub"
    ).strip() or "LoanHub"
    use_ssl = _as_bool(
        configuration.get("use_ssl", os.getenv("CONTRACT_EMAIL_SMTP_SSL")),
        default=port == 465,
    )
    starttls = _as_bool(
        configuration.get("starttls", os.getenv("CONTRACT_EMAIL_SMTP_STARTTLS")),
        default=not use_ssl,
    )

    integration_enabled = bool(row and row.is_enabled)
    environment_configured = bool(os.getenv("CONTRACT_EMAIL_SMTP_HOST"))
    if not host or not from_email or not (integration_enabled or environment_configured):
        return None
    if username and not password:
        return None

    return EmailTransport(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        from_name=from_name,
        use_ssl=use_ssl,
        starttls=starttls,
    )


def email_transport_ready(db: Session, company_id: Any) -> bool:
    return _email_configuration(db, company_id) is not None


def _otp_digest(contract_id: Any, reference: str, otp: str) -> str:
    payload = f"{contract_id}:{reference}:{otp}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _send_otp_email(
    transport: EmailTransport,
    *,
    recipient: str,
    borrower_name: str,
    contract_number: str,
    company_name: str,
    otp: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = f"LoanHub contract signing code - {contract_number}"
    message["From"] = f"{transport.from_name} <{transport.from_email}>"
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                f"Dear {borrower_name},",
                "",
                f"{company_name} has requested your signature for LoanHub contract {contract_number}.",
                f"Your one-time signing code is: {otp}",
                "",
                f"This code expires in {OTP_TTL_MINUTES} minutes and can be used only once.",
                "Do not share the code unless you are actively reviewing and signing this contract.",
                "If you did not expect this request, contact the lender and do not provide the code.",
                "",
                "LoanHub",
            ]
        )
    )

    context = ssl.create_default_context()
    if transport.use_ssl:
        with smtplib.SMTP_SSL(transport.host, transport.port, timeout=10, context=context) as smtp:
            if transport.username:
                smtp.login(transport.username, transport.password or "")
            smtp.send_message(message)
        return

    with smtplib.SMTP(transport.host, transport.port, timeout=10) as smtp:
        smtp.ehlo()
        if transport.starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if transport.username:
            smtp.login(transport.username, transport.password or "")
        smtp.send_message(message)


def _pending_session(db: Session, contract: LoanContract, *, lock: bool = False) -> CompanyOperatingRecord | None:
    query = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.company_id == contract.company_id,
            CompanyOperatingRecord.loan_id == contract.loan_id,
            CompanyOperatingRecord.module == MODULE,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
            CompanyOperatingRecord.status == "pending",
            CompanyOperatingRecord.is_archived.is_(False),
        )
        .order_by(CompanyOperatingRecord.created_at.desc())
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def signing_status(db: Session, contract: LoanContract) -> dict[str, Any]:
    name, email = _borrower_identity(db, contract)
    session = _pending_session(db, contract)
    now = _utcnow_naive()
    pending = bool(session and session.due_at and session.due_at > now)
    return {
        "contract_id": str(contract.id),
        "borrower_name": name,
        "masked_email": mask_email(email),
        "email_transport_ready": email_transport_ready(db, contract.company_id),
        "pending": pending,
        "expires_at": session.due_at.isoformat() + "Z" if pending and session and session.due_at else None,
        "attempts_remaining": max(0, MAX_ATTEMPTS - int((session.data or {}).get("attempts", 0))) if pending and session else MAX_ATTEMPTS,
    }


def request_signing_code(
    db: Session,
    *,
    contract: LoanContract,
    requested_by_user_id: Any,
) -> dict[str, Any]:
    if contract.locked_at or contract.status == "signed":
        raise HTTPException(status_code=409, detail="The signed contract is locked.")
    if contract.borrower_signed_at:
        raise HTTPException(status_code=409, detail="The borrower has already signed this contract.")

    borrower_name, recipient = _borrower_identity(db, contract)
    transport = _email_configuration(db, contract.company_id)
    if transport is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Email + OTP signing is not configured. Enable the company Email integration with SMTP settings "
                "or configure the CONTRACT_EMAIL_SMTP_* production environment values."
            ),
        )

    now = _utcnow_naive()
    existing = _pending_session(db, contract, lock=True)
    if existing and existing.created_at and (now - existing.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        retry_after = max(1, RESEND_COOLDOWN_SECONDS - int((now - existing.created_at).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="A signing code was sent recently. Use that code or request another after the cooldown.",
            headers={"Retry-After": str(retry_after)},
        )
    if existing:
        existing.status = "superseded"
        existing.is_archived = True
        db.add(existing)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)
    reference = f"ESIGN-{str(contract.id)[:8].upper()}-{secrets.token_hex(5).upper()}"
    record = CompanyOperatingRecord(
        company_id=contract.company_id,
        branch_id=contract.loan.branch_id if contract.loan else None,
        module=MODULE,
        record_type=RECORD_TYPE,
        reference=reference,
        title=f"Email OTP signature - {contract.contract_number}",
        description="Borrower Email + OTP signing challenge",
        status="pending",
        priority="high",
        borrower_id=contract.borrower_id,
        loan_id=contract.loan_id,
        created_by_user_id=requested_by_user_id,
        counterparty_name=borrower_name,
        due_at=expires_at,
        data={
            "contract_id": str(contract.id),
            "contract_number": contract.contract_number,
            "contract_hash": contract.contract_hash,
            "otp_digest": _otp_digest(contract.id, reference, otp),
            "attempts": 0,
            "masked_email": mask_email(recipient),
            "email_hash": hashlib.sha256(recipient.encode("utf-8")).hexdigest(),
            "requested_at": now.isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z",
            "requested_by_user_id": str(requested_by_user_id),
        },
        tags=["contract", "signature", "email", "otp"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    snapshot = contract.terms_snapshot if isinstance(contract.terms_snapshot, dict) else {}
    company_snapshot = snapshot.get("company") if isinstance(snapshot.get("company"), dict) else {}
    company_name = str((company_snapshot or {}).get("name") or "Your lender")
    try:
        _send_otp_email(
            transport,
            recipient=recipient,
            borrower_name=borrower_name,
            contract_number=contract.contract_number,
            company_name=company_name,
            otp=otp,
        )
    except (OSError, smtplib.SMTPException) as exc:
        record.status = "delivery_failed"
        failed_data = dict(record.data or {})
        failed_data["delivery_error"] = type(exc).__name__
        failed_data["delivery_failed_at"] = _utcnow_naive().isoformat() + "Z"
        record.data = failed_data
        db.add(record)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="The signing code could not be delivered by the configured email service.",
        ) from exc

    sent_data = dict(record.data or {})
    sent_data["delivered_at"] = _utcnow_naive().isoformat() + "Z"
    record.data = sent_data
    db.add(record)
    db.commit()

    return {
        "status": "sent",
        "contract_id": str(contract.id),
        "masked_email": mask_email(recipient),
        "expires_at": expires_at.isoformat() + "Z",
        "attempts_remaining": MAX_ATTEMPTS,
    }


def verify_signing_code(
    db: Session,
    *,
    contract: LoanContract,
    otp: str,
    verified_by_user_id: Any,
) -> dict[str, Any]:
    if contract.locked_at or contract.status == "signed":
        raise HTTPException(status_code=409, detail="The signed contract is locked.")
    if contract.borrower_signed_at:
        raise HTTPException(status_code=409, detail="The borrower has already signed this contract.")
    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=422, detail="Enter the six-digit signing code.")

    record = _pending_session(db, contract, lock=True)
    if not record:
        raise HTTPException(status_code=409, detail="Request a new Email + OTP signing code first.")

    now = _utcnow_naive()
    if not record.due_at or record.due_at <= now:
        record.status = "expired"
        record.is_archived = True
        db.add(record)
        db.commit()
        raise HTTPException(status_code=410, detail="The signing code has expired. Request a new code.")

    data = dict(record.data or {})
    attempts = int(data.get("attempts", 0))
    if attempts >= MAX_ATTEMPTS:
        record.status = "locked"
        record.is_archived = True
        db.add(record)
        db.commit()
        raise HTTPException(status_code=423, detail="Too many incorrect signing-code attempts. Request a new code.")

    candidate = _otp_digest(contract.id, record.reference, otp)
    expected = str(data.get("otp_digest") or "")
    if not expected or not hmac.compare_digest(candidate, expected):
        attempts += 1
        data["attempts"] = attempts
        data["last_failed_attempt_at"] = now.isoformat() + "Z"
        record.data = data
        if attempts >= MAX_ATTEMPTS:
            record.status = "locked"
            record.is_archived = True
        db.add(record)
        db.commit()
        if attempts >= MAX_ATTEMPTS:
            raise HTTPException(status_code=423, detail="Too many incorrect signing-code attempts. Request a new code.")
        raise HTTPException(
            status_code=422,
            detail=f"The signing code is incorrect. {MAX_ATTEMPTS - attempts} attempt(s) remaining.",
        )

    borrower_name, recipient = _borrower_identity(db, contract)
    contract.borrower_signature_name = borrower_name
    contract.borrower_signature_method = "email_otp"
    contract.borrower_signed_at = datetime.now(timezone.utc)
    update_contract_status(contract)

    data.pop("otp_digest", None)
    data["attempts"] = attempts + 1
    data["verified_at"] = now.isoformat() + "Z"
    data["verified_by_user_id"] = str(verified_by_user_id)
    data["signature_method"] = "email_otp"
    data["verified_email_hash"] = hashlib.sha256(recipient.encode("utf-8")).hexdigest()
    data["evidence_hash"] = hashlib.sha256(
        f"{contract.id}:{contract.contract_hash}:{record.reference}:{data['verified_at']}".encode("utf-8")
    ).hexdigest()
    record.data = data
    record.status = "verified"
    record.is_archived = True
    db.add(contract)
    db.add(record)

    refresh_contract_pdf_after_signature(
        db,
        contract=contract,
        requested_by_user_id=verified_by_user_id,
    )
    db.commit()
    db.refresh(contract)

    return {
        "status": "verified",
        "contract_id": str(contract.id),
        "contract_status": contract.status,
        "borrower_signed_at": contract.borrower_signed_at.isoformat() if contract.borrower_signed_at else None,
        "signature_method": "email_otp",
        "masked_email": mask_email(recipient),
        "evidence_reference": record.reference,
    }
