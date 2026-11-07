"""Opt-in isolated PostgreSQL tests for actual Wacom review SQL predicates.

Requires WACOM_PG_TEST_URL with a loopback host and database ending '_test'.
Creates and drops only a unique, disposable schema. Never connects to prod.
The minimal copied tables deliberately have no production FKs or RLS policies:
these tests prove SQL tenant filtering/row locks/audit transactions, NOT RLS.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import Column, MetaData, Table, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.file_management import ManagedFile
from routers import local_signature_review as review


def _test_db_url():
    raw = os.getenv("WACOM_PG_TEST_URL")
    if not raw:
        pytest.skip("WACOM_PG_TEST_URL not provided; isolated PostgreSQL test is opt-in")
    parsed = make_url(raw)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"127.0.0.1", "localhost", "::1"}
        or not parsed.database
        or not parsed.database.endswith("_test")
    ):
        pytest.fail("WACOM_PG_TEST_URL must be loopback PostgreSQL database ending _test")
    return raw


@pytest.fixture
def postgres_review_db():
    url = _test_db_url()
    engine = create_engine(url, pool_size=1, max_overflow=0)
    schema = "wacom_test_" + uuid4().hex
    connection = engine.connect()
    try:
        # Unique literal schema name generated exclusively from uuid4 hex.
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.commit()
        connection.execute(text(f'SET search_path TO "{schema}"'))
        connection.commit()

        metadata = MetaData()
        for source in (ManagedFile.__table__, AuditLog.__table__):
            # Test only the real ORM table shape without creating the much
            # larger LoanHub dependency graph in a disposable database.
            Table(
                source.name, metadata,
                *[
                    Column(
                        column.name,
                        column.type,
                        primary_key=column.primary_key,
                        nullable=column.nullable if not column.primary_key else False,
                        default=column.default,
                        server_default=column.server_default,
                    )
                    for column in source.columns
                ],
            )
        metadata.create_all(connection, checkfirst=False)
        connection.commit()
        db = Session(bind=connection, expire_on_commit=False)
        try:
            yield db
        finally:
            db.close()
    finally:
        try:
            connection.rollback()
            connection.execute(text('SET search_path TO public'))
            connection.commit()
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            connection.commit()
        finally:
            connection.close()
            engine.dispose()


def _capture(company_id, operator_id, signer_id):
    return ManagedFile(
        id=uuid4(),
        owner_user_id=operator_id,
        company_id=company_id,
        branch_id=None,
        reference="TEST-" + uuid4().hex[:12],
        original_name="synthetic.png",
        stored_name=uuid4().hex + ".bin",
        storage_key=str(company_id) + "/" + uuid4().hex + ".bin",
        storage_provider="local",
        mime_type="image/png",
        detected_mime_type="image/png",
        extension="png",
        size_bytes=90,
        checksum_sha256="a" * 64,
        is_encrypted=True,
        encryption_nonce="test-only-nonce",
        encryption_version="aesgcm-v1",
        scan_status="clean",
        category="wacom_client_signature_pending",
        visibility="private",
        linked_entity_type="wacom_client",
        linked_entity_id=str(signer_id),
        is_confidential=True,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
    )


def _context(company_id, user_id):
    role = next(iter(review.COMPANY_MANAGEMENT_ROLES))
    return SimpleNamespace(
        company_id=company_id,
        branch_id=None,
        staff=SimpleNamespace(role=role),
        user=SimpleNamespace(id=user_id),
        role=role,
    )


def test_postgres_review_queue_and_independent_decision_are_tenant_scoped(
    postgres_review_db, monkeypatch,
):
    db = postgres_review_db
    tenant_a, tenant_b = uuid4(), uuid4()
    owner_a, owner_b, reviewer_a = uuid4(), uuid4(), uuid4()
    record_a = _capture(tenant_a, owner_a, uuid4())
    record_b = _capture(tenant_b, owner_b, uuid4())
    db.add_all([record_a, record_b])
    db.commit()
    monkeypatch.setattr(review, "require_tenant_roles", lambda *_: None)

    a_context = _context(tenant_a, reviewer_a)
    queue_a = review.pending_evidence(Response(), 50, db, a_context)
    assert [row["capture_file_id"] for row in queue_a["captures"]] == [str(record_a.id)]
    assert queue_a["captures"][0]["usable_for_signing"] is False

    # Cannot review a different tenant's capture even with its UUID.
    payload = review.EvidenceDecision(
        decision="verify",
        identity_checked=True,
        consent_checked=True,
        evidence_reference="TEST-ONLY-REVIEW-0001",
        reason="Synthetic identity and consent evidence",
    )
    with pytest.raises(HTTPException) as exc:
        review.review_capture(record_b.id, payload, Response(), db, a_context)
    assert exc.value.status_code == 404

    # Uploader cannot self-approve.
    with pytest.raises(HTTPException) as exc:
        review.review_capture(
            record_a.id, payload, Response(), db, _context(tenant_a, owner_a)
        )
    assert exc.value.status_code == 403

    result = review.review_capture(record_a.id, payload, Response(), db, a_context)
    assert result["evidence_status"] == "verified"
    assert result["usable_for_signing"] is False
    assert db.get(ManagedFile, record_b.id).category == "wacom_client_signature_pending"

    audits = db.query(AuditLog).filter(
        AuditLog.company_id == tenant_a,
        AuditLog.record_id == record_a.id,
        AuditLog.action == "local_signatures.capture_reviewed",
    ).all()
    assert len(audits) == 1
    assert audits[0].user_id == reviewer_a
    assert audits[0].event_data["authorizes_signing"] is False

    # A second decision cannot silently change previously reviewed evidence.
    with pytest.raises(HTTPException) as exc:
        review.review_capture(record_a.id, payload, Response(), db, a_context)
    assert exc.value.status_code == 404


def test_postgres_review_preview_filters_tenant_before_reading_blob(
    postgres_review_db, monkeypatch,
):
    db = postgres_review_db
    tenant_a, tenant_b, owner_a = uuid4(), uuid4(), uuid4()
    file_a = _capture(tenant_a, owner_a, uuid4())
    file_b = _capture(tenant_b, uuid4(), uuid4())
    db.add_all([file_a, file_b])
    db.commit()
    monkeypatch.setattr(review, "require_tenant_roles", lambda *_: None)
    reads = []
    # We don't need actual storage here; other tests cover encrypted bytes.
    def reader(record):
        reads.append(record.id)
        return b"x" * record.size_bytes
    monkeypatch.setattr(review, "read_file_bytes", reader)
    context = _context(tenant_a, uuid4())
    with pytest.raises(HTTPException) as exc:
        review.preview_capture(file_b.id, db, context)
    assert exc.value.status_code == 404
    assert reads == []
    result = review.preview_capture(file_a.id, db, context)
    assert result.media_type == "image/png"
    assert result.headers["cache-control"] == "private, no-store"
    assert reads == [file_a.id]
