from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from database.models.enums import UserRole
from database.models.user import User
from database.session import get_db


logger = logging.getLogger("loanhub.bootstrap.superadmin")

DEFAULT_SUPERADMIN_EMAIL = "thekoetlisi@gmail.com"
DEFAULT_SUPERADMIN_PHONE = "59001394"


def _environment_flag(name: str, default: bool = True) -> bool:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _required_password() -> str:
    password = os.getenv("BOOTSTRAP_SUPERADMIN_PASSWORD", "")

    if not password:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_PASSWORD must be configured because "
            "LoanHub does not currently have a super-admin user."
        )

    if len(password) < 12:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_PASSWORD must contain at least "
            "12 characters."
        )

    return password


def _configured_email() -> str:
    email = os.getenv(
        "BOOTSTRAP_SUPERADMIN_EMAIL",
        DEFAULT_SUPERADMIN_EMAIL,
    ).strip().lower()

    if not email:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_EMAIL cannot be empty."
        )

    return email


def _configured_phone() -> str:
    phone = os.getenv(
        "BOOTSTRAP_SUPERADMIN_PHONE",
        DEFAULT_SUPERADMIN_PHONE,
    ).strip()

    if not phone:
        raise RuntimeError(
            "BOOTSTRAP_SUPERADMIN_PHONE cannot be empty."
        )

    return phone


def ensure_superadmin_exists() -> User | None:
    """
    Create the first platform super-admin when none exists.

    This operation is idempotent:
    - Existing super-admin accounts are never modified.
    - Only one account is created.
    - Passwords are hashed with LoanHub's existing security utility.
    - Plain-text passwords are never logged.
    """

    if not _environment_flag(
        "BOOTSTRAP_SUPERADMIN_ENABLED",
        default=True,
    ):
        logger.info(
            "Automatic super-admin bootstrap is disabled."
        )
        return None

    database_provider = get_db()
    db: Session | None = None

    try:
        db = next(database_provider)

        existing_superadmin = (
            db.query(User)
            .filter(User.role == UserRole.SUPERADMIN)
            .first()
        )

        if existing_superadmin is not None:
            logger.info(
                "Super-admin bootstrap skipped because at least one "
                "super-admin already exists."
            )
            return existing_superadmin

        email = _configured_email()
        phone = _configured_phone()
        password = _required_password()

        conflicting_user = (
            db.query(User)
            .filter(
                or_(
                    User.email == email,
                    User.phone == phone,
                )
            )
            .first()
        )

        if conflicting_user is not None:
            if conflicting_user.role == UserRole.SUPERADMIN:
                logger.info(
                    "The configured account is already a super-admin."
                )
                return conflicting_user

            raise RuntimeError(
                "LoanHub has no super-admin, but the configured "
                "bootstrap email or phone belongs to another user. "
                "Resolve that account conflict before startup."
            )

        superadmin = User(
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=UserRole.SUPERADMIN,
            is_active=True,
            is_verified=True,
        )

        db.add(superadmin)
        db.commit()
        db.refresh(superadmin)

        logger.warning(
            "Initial LoanHub super-admin created successfully: %s",
            email,
        )

        return superadmin

    except IntegrityError as exc:
        if db is not None:
            db.rollback()

            # Another worker may have created the account while this
            # worker was processing the startup operation.
            existing_superadmin = (
                db.query(User)
                .filter(User.role == UserRole.SUPERADMIN)
                .first()
            )

            if existing_superadmin is not None:
                logger.info(
                    "Another application worker created the initial "
                    "super-admin."
                )
                return existing_superadmin

        raise RuntimeError(
            "The initial super-admin could not be created because "
            "the configured email or phone conflicts with an "
            "existing account."
        ) from exc

    except Exception:
        if db is not None:
            db.rollback()

        logger.exception(
            "LoanHub initial super-admin bootstrap failed."
        )
        raise

    finally:
        database_provider.close()


def install_superadmin_bootstrap(app: FastAPI) -> None:
    """
    Wrap FastAPI's existing lifespan without replacing its current
    startup or shutdown behaviour.
    """

    installation_key = "_loanhub_superadmin_bootstrap_installed"

    if getattr(app.state, installation_key, False):
        return

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def bootstrap_lifespan(
        application: FastAPI,
    ):
        async with original_lifespan(application) as lifespan_state:
            # Run synchronous SQLAlchemy and password hashing outside
            # the event loop.
            await asyncio.to_thread(ensure_superadmin_exists)

            yield lifespan_state

    app.router.lifespan_context = bootstrap_lifespan
    setattr(app.state, installation_key, True)
