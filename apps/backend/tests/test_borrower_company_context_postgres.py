"""PostgreSQL-executed tenant isolation for the REAL borrower-context handler.

Uses temporary PostgreSQL tables in a rolled-back transaction and maps the
handler's three production ORM classes to equivalent disposable tables.
No customer records, production DB, or production sessions are used.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, ForeignKey, create_engine, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, declarative_base

from database.models.enums import UserRole
from routers import auth


def test_real_postgresql_company_borrower_query_isolation(monkeypatch):
    url = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL integration URL not configured")

    engine = create_engine(url, pool_pre_ping=True)
    base = declarative_base()
    company_a, company_b, inactive_company = uuid4(), uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    borrower_a, borrower_b = uuid4(), uuid4()

    class CompanyRow(base):
        __tablename__ = "phase47_companies"
        id = Column(UUID(as_uuid=True), primary_key=True)
        is_active = Column(Boolean, nullable=False)

    class BorrowerRow(base):
        __tablename__ = "phase47_borrowers"
        id = Column(UUID(as_uuid=True), primary_key=True)
        user_id = Column(UUID(as_uuid=True), nullable=False)

    class LoanRow(base):
        __tablename__ = "phase47_loans"
        id = Column(UUID(as_uuid=True), primary_key=True)
        borrower_id = Column(UUID(as_uuid=True), ForeignKey("phase47_borrowers.id"), nullable=False)
        company_id = Column(UUID(as_uuid=True), ForeignKey("phase47_companies.id"), nullable=False)

    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                # PG TEMP tables are scoped to this connection and are never
                # committed; table names intentionally do not overlap LoanHub.
                base.metadata.create_all(conn, tables=[], checkfirst=False)
                conn.execute(text("""CREATE TEMP TABLE phase47_companies (
                    id uuid PRIMARY KEY, is_active boolean NOT NULL
                ) ON COMMIT DROP"""))
                conn.execute(text("""CREATE TEMP TABLE phase47_borrowers (
                    id uuid PRIMARY KEY, user_id uuid NOT NULL
                ) ON COMMIT DROP"""))
                conn.execute(text("""CREATE TEMP TABLE phase47_loans (
                    id uuid PRIMARY KEY, borrower_id uuid NOT NULL
                        REFERENCES phase47_borrowers(id),
                    company_id uuid NOT NULL REFERENCES phase47_companies(id)
                ) ON COMMIT DROP"""))
                conn.execute(CompanyRow.__table__.insert(), [
                    {"id": company_a, "is_active": True},
                    {"id": company_b, "is_active": True},
                    {"id": inactive_company, "is_active": False},
                ])
                conn.execute(BorrowerRow.__table__.insert(), [
                    {"id": borrower_a, "user_id": user_a},
                    {"id": borrower_b, "user_id": user_b},
                ])
                conn.execute(LoanRow.__table__.insert(), [
                    {"id": uuid4(), "borrower_id": borrower_a, "company_id": company_a},
                    {"id": uuid4(), "borrower_id": borrower_b, "company_id": company_b},
                    {"id": uuid4(), "borrower_id": borrower_a, "company_id": inactive_company},
                ])

                monkeypatch.setattr(auth, "Borrower", BorrowerRow)
                monkeypatch.setattr(auth, "ClientCompanyLoan", LoanRow)
                monkeypatch.setattr(auth, "LoanCompany", CompanyRow)
                session_jti = str(uuid4())
                claims = {"user_id": str(user_a), "token_type": "access", "session_jti": session_jti}
                monkeypatch.setattr(auth, "decode_token", lambda _: claims)
                actor = SimpleNamespace(
                    id=user_a, role=UserRole.BORROWER, is_active=True,
                    is_verified=True, must_change_password=False,
                )
                with Session(bind=conn) as db:
                    def check(company):
                        return auth.borrower_company_context(
                            company_id=company,
                            current_user=actor, token="test-session", db=db,
                        )
                    result = check(company_a)
                    assert result.user_id == user_a
                    assert result.borrower_id == borrower_a
                    assert result.company_id == company_a

                    for forbidden in (company_b, inactive_company, uuid4()):
                        with pytest.raises(HTTPException) as exc:
                            check(forbidden)
                        assert exc.value.status_code == 404

                    # Even for a company with a loan, a different borrower
                    # cannot prove ownership of its existing loan.
                    actor.id = user_b
                    claims["user_id"] = str(user_b)
                    with pytest.raises(HTTPException) as exc:
                        check(company_a)
                    assert exc.value.status_code == 404

                    # Session token missing JTI cannot reach the query.
                    claims["session_jti"] = ""
                    with pytest.raises(HTTPException) as exc:
                        check(company_b)
                    assert exc.value.status_code == 401
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_real_postgres_revocation_state_and_jti_are_enforced(monkeypatch):
    """Exercise the actual LoanHub local-auth dependency with disposable PG."""
    from core import security

    url = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL integration URL not configured")

    engine = create_engine(url, pool_pre_ping=True)
    base = declarative_base()
    user_id = uuid4()
    jti = str(uuid4())

    class SecurityRow(base):
        __tablename__ = "phase47_security"
        user_id = Column(UUID(as_uuid=True), primary_key=True)
        session_version = Column("session_version", __import__("sqlalchemy").Integer, nullable=False)

    class TokenRow(base):
        __tablename__ = "phase47_tokens"
        id = Column(UUID(as_uuid=True), primary_key=True)
        user_id = Column(UUID(as_uuid=True), nullable=False)
        jti = Column(__import__("sqlalchemy").String(120), nullable=False)
        revoked = Column(Boolean, nullable=False)

    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text("""CREATE TEMP TABLE phase47_security (
                    user_id uuid PRIMARY KEY, session_version integer NOT NULL
                ) ON COMMIT DROP"""))
                conn.execute(text("""CREATE TEMP TABLE phase47_tokens (
                    id uuid PRIMARY KEY, user_id uuid NOT NULL,
                    jti varchar(120) NOT NULL, revoked boolean NOT NULL
                ) ON COMMIT DROP"""))
                conn.execute(SecurityRow.__table__.insert(), [
                    {"user_id": user_id, "session_version": 1},
                ])
                conn.execute(TokenRow.__table__.insert(), [
                    {"id": uuid4(), "user_id": user_id, "jti": jti, "revoked": False},
                ])
                actor = SimpleNamespace(id=user_id)
                monkeypatch.setattr(security, "_load_user", lambda db, uid: actor if uid == user_id else None)
                monkeypatch.setattr(security, "UserSecurityState", SecurityRow)
                monkeypatch.setattr(security, "RefreshToken", TokenRow)
                claims = {"user_id": str(user_id), "session_version": 1, "session_jti": jti}
                monkeypatch.setattr(security, "decode_token", lambda _: claims)

                with Session(bind=conn) as db:
                    assert security._current_local_user("dummy-signed-token", db) is actor

                    # Revocation of the exact JTI invalidates the still-valid
                    # access token without relying on token expiry.
                    conn.execute(text(
                        "UPDATE phase47_tokens SET revoked = TRUE WHERE jti = :jti"
                    ), {"jti": jti})
                    with pytest.raises(HTTPException) as exc:
                        security._current_local_user("dummy-signed-token", db)
                    assert exc.value.status_code == 401

                    conn.execute(text(
                        "UPDATE phase47_tokens SET revoked = FALSE WHERE jti = :jti"
                    ), {"jti": jti})
                    assert security._current_local_user("dummy-signed-token", db) is actor

                    # Session-version rotation revokes all old access tokens.
                    conn.execute(text(
                        "UPDATE phase47_security SET session_version = 2"
                    ))
                    db.expire_all()  # Force real SQL read after out-of-session update.
                    with pytest.raises(HTTPException) as exc:
                        security._current_local_user("dummy-signed-token", db)
                    assert exc.value.status_code == 401
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
