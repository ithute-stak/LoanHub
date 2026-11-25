"""Disposable PostgreSQL-only HTTP certification for Batlokoa Save Client.

This router is intentionally NEVER included in api.v1.router and has no
production activation path. It lets an explicitly acknowledged, isolated
*_sandbox database exercise the real new-only atomic command through HTTP.

Never mount this module in a live application. The normal registration
endpoint stays unmounted and hard-denied until an independent release.
"""
from __future__ import annotations

import os
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from routers.batlokoa_new_only_registration_command import NewOnlyClientReceipt
from services.atomic_new_client_registration import AtomicRegistrationUnavailable
from services.batlokoa_new_only_registration_command import (
    BatlokoaRegistrationNotReleased, submit_new_only_client,
)
from services.full_new_only_client_staging import FullNewOnlyStagingUnavailable
from services.new_client_registration_idempotency import (
    IdempotencyConflict, IdempotencyUnavailable,
)

ACK_ENV = "LOANHUB_REGISTRATION_E2E_ACK"
ACK_VALUE = "isolated_disposable_database"


def build_offline_certification_router(
    *, session_factory: Callable[[], Session], fingerprint_secret: bytes,
) -> APIRouter:
    """Construct a test-only router; no production route registry imports it.

    The sandbox check takes place before invoking the real command. Two
    independent guards (operator ACK and actual PostgreSQL database name)
    cannot be supplied through HTTP headers or the request body.
    """
    router = APIRouter(
        prefix="/batlokoa/registration",
        tags=["Offline Registration Certification"],
    )

    @router.post(
        "/clients", response_model=NewOnlyClientReceipt,
        status_code=status.HTTP_201_CREATED,
    )
    def submit_certification_registration(
        payload: FullNewOnlyClientCapture,
        context: TenantContext = Depends(get_tenant_context),
        idempotency_key: str | None = Header(
            default=None, alias="Idempotency-Key",
        ),
    ) -> NewOnlyClientReceipt:
        unavailable = HTTPException(
            status_code=503,
            detail={"code": "OFFLINE_CERTIFICATION_UNAVAILABLE"},
        )
        if os.environ.get(ACK_ENV) != ACK_VALUE:
            raise unavailable
        if not isinstance(fingerprint_secret, bytes) or len(fingerprint_secret) < 32:
            raise unavailable
        # Inspection has its own read-only transaction; the real writer uses
        # a fresh dedicated transaction only after the database is proven
        # to be a disposable sandbox.
        try:
            with session_factory() as check:
                bind = check.get_bind()
                if bind is None or bind.dialect.name != "postgresql":
                    raise unavailable
                with check.begin():
                    check.execute(text("SET TRANSACTION READ ONLY"))
                    database_name = check.execute(
                        text("SELECT current_database()")
                    ).scalar_one()
            if (
                not isinstance(database_name, str)
                or not database_name.endswith("_sandbox")
            ):
                raise unavailable
        except HTTPException:
            raise
        except Exception:
            raise unavailable from None

        if not isinstance(idempotency_key, str) or not (
            16 <= len(idempotency_key) <= 128
        ) or not all(
            c.isascii() and (c.isalnum() or c in "-_.")
            for c in idempotency_key
        ):
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_IDEMPOTENCY_KEY"},
            )
        try:
            receipt = submit_new_only_client(
                context=context,
                payload=payload,
                idempotency_key=idempotency_key,
                fingerprint_secret=fingerprint_secret,
                session_factory=session_factory,
                independently_approved_release=True,  # isolated sandbox only
            )
        except IdempotencyConflict:
            raise HTTPException(
                status_code=409, detail={"code": "REGISTRATION_CONFLICT"},
            ) from None
        except IntegrityError:
            raise HTTPException(
                status_code=409, detail={"code": "REGISTRATION_CONFLICT"},
            ) from None
        except (ValueError, FullNewOnlyStagingUnavailable):
            raise HTTPException(
                status_code=422, detail={"code": "REGISTRATION_REJECTED"},
            ) from None
        except (
            AtomicRegistrationUnavailable, IdempotencyUnavailable,
            BatlokoaRegistrationNotReleased,
        ):
            raise unavailable from None
        except Exception:
            # Do not return SQL errors, borrower values or financial details.
            raise unavailable from None
        return NewOnlyClientReceipt(
            client_account_id=receipt.client_account_id,
            replayed=receipt.replayed,
        )

    return router
