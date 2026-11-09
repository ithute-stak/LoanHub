"""End-to-end synthetic PDF rendering -> final archive commit validation.

Reproduces the real ordering: persist candidate metadata, bind its ID/hash to
a RESERVED receipt, then run the final safety gate before SQL COMMIT.
No loan is signed or database mutated by this test.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services.wacom_approved_field import bind_approved_field
from services.wacom_final_pdf_candidate import render_final_pdf_candidate
from services import wacom_execution_commit_policy as policy


def fixture():
    source_buf = BytesIO()
    doc = canvas.Canvas(source_buf, pagesize=(612, 792))
    doc.drawString(100, 650, "Synthetic loan contract - no actual borrower")
    doc.save()
    original_pdf = source_buf.getvalue()
    ink = Image.new("RGBA", (250, 75), (255, 255, 255, 0))
    draw = ImageDraw.Draw(ink)
    draw.line([(12, 62), (105, 13), (222, 52)], fill=(0, 0, 0, 255), width=4)
    ink_buf = BytesIO()
    ink.save(ink_buf, format="PNG")
    handwriting = ink_buf.getvalue()
    source_digest = sha256(original_pdf).hexdigest()
    evidence_digest = sha256(handwriting).hexdigest()
    field, field_digest = bind_approved_field(
        source_pdf=original_pdf, expected_sha256=source_digest,
        page_index=0, expected_page_count=1, x=110, y=180,
        width=270, height=90,
    )
    now = datetime.now(timezone.utc)
    tenant = uuid4()
    intent = R(
        id=uuid4(), company_id=tenant, contract_id=uuid4(),
        source_file_id=uuid4(), borrower_id=uuid4(),
        document_sha256=source_digest, evidence_sha256=evidence_digest,
        binding_sha256="c"*64,
    )
    authorization = R(
        id=uuid4(), company_id=tenant, intent_id=intent.id,
        contract_id=intent.contract_id, status="approved",
        authorized_by=uuid4(), authorized_at=now-timedelta(seconds=5),
        expires_at=now+timedelta(minutes=1), consumed_at=None,
        document_sha256=source_digest, evidence_sha256=evidence_digest,
        field_binding_sha256=field_digest,
        field_page_index=field.page_index, field_page_count=field.page_count,
        field_x=field.x, field_y=field.y,
        field_width=field.width, field_height=field.height,
    )
    candidate_pdf, candidate_digest = render_final_pdf_candidate(
        source_pdf=original_pdf, handwriting_png=handwriting,
        authorization=authorization, expected_source_sha256=source_digest,
        expected_handwriting_sha256=evidence_digest,
    )
    candidate_file = R(
        id=uuid4(), company_id=tenant, is_deleted=False, is_encrypted=True,
        is_confidential=True, scan_status="clean", mime_type="application/pdf",
        category="wacom_execution_candidate", checksum_sha256=candidate_digest,
    )
    packet = R(id=uuid4(), packet_file_id=uuid4())
    operator = uuid4()
    receipt = R(
        company_id=tenant, contract_id=intent.contract_id,
        intent_id=intent.id, authorization_id=authorization.id,
        packet_id=packet.id, status="reserved", executed_at=None,
        executed_file_id=candidate_file.id, executed_pdf_sha256=candidate_digest,
        document_sha256=source_digest, evidence_sha256=evidence_digest,
        binding_sha256=intent.binding_sha256,
        field_binding_sha256=field_digest,
        reserved_by=operator, reserved_at=now,
    )
    options = dict(
        intent=intent, approval=R(), packet=packet,
        execution_authorization=authorization, receipt=receipt,
        contract=R(), source=R(), evidence=R(),
        candidate_file=candidate_file, executing_user_id=operator,
        source_pdf=original_pdf, handwriting_png=handwriting,
        candidate_pdf=candidate_pdf, candidate_sha256=candidate_digest, now=now,
    )
    return options, original_pdf


@pytest.fixture(autouse=True)
def isolate_upstream_preflight(monkeypatch):
    # Upstream preflight is separately tested; this test exercises actual
    # PDF placement plus *real* final receipt/file/field/hash validation.
    monkeypatch.setattr(policy, "reserve_execution_blockers", lambda **kw: [])


def test_real_pdf_render_then_bound_candidate_receipt_passes_commit_gate():
    options, original_pdf = fixture()
    assert policy.execution_commit_blockers(**options) == []
    assert options["receipt"].executed_file_id == options["candidate_file"].id
    assert options["receipt"].executed_at is None
    assert options["receipt"].status == "reserved"
    parsed = PdfReader(BytesIO(options["candidate_pdf"]))
    assert len(parsed.pages) == 1
    assert len(parsed.pages[0].images) >= 1
    assert options["candidate_pdf"] != original_pdf


def test_missing_candidate_reference_fails_closed():
    options, _ = fixture()
    options["receipt"].executed_file_id = None
    assert "execution_receipt_not_bound_to_candidate" in policy.execution_commit_blockers(**options)


def test_receipt_to_other_pdf_or_tenant_fails_closed():
    options, _ = fixture()
    options["receipt"].executed_file_id = uuid4()
    assert "execution_receipt_not_bound_to_candidate" in policy.execution_commit_blockers(**options)
    options, _ = fixture()
    options["candidate_file"].company_id = uuid4()
    assert "candidate_storage_not_verified" in policy.execution_commit_blockers(**options)


def test_candidate_bytes_changed_after_storage_fails_closed():
    options, _ = fixture()
    options["candidate_pdf"] += b"unapproved change"
    assert "rendered_candidate_hash_mismatch" in policy.execution_commit_blockers(**options)


def test_no_double_execution_or_reusing_original_contract():
    options, _ = fixture()
    options["receipt"].status = "executed"
    assert "execution_receipt_not_bound_to_candidate" in policy.execution_commit_blockers(**options)
    options, _ = fixture()
    options["candidate_file"].id = options["intent"].source_file_id
    assert "candidate_overwrites_original" in policy.execution_commit_blockers(**options)


def test_real_archive_route_returns_unsigned_candidate_and_exact_retry(monkeypatch):
    """Drive the actual endpoint through PDF rendering, receipt and two requests.

    Storage and database boundaries are fakes; the renderer and final commit
    gate are real. This is synthetic, not an authenticated HTTP/hardware test.
    """
    from fastapi import Response
    from database.models.file_management import ManagedFile
    from database.models.origination import LoanContract
    from database.models.wacom_execution_authorization import WacomExecutionAuthorization
    from database.models.wacom_execution_receipt import WacomExecutionReceipt
    from database.models.enums import UserRole
    from routers import wacom_pdf_candidates as endpoint

    values, _ = fixture()
    intent = values["intent"]
    authorization = values["execution_authorization"]
    tenant = intent.company_id
    # Completely independent actors for archive vs prior review/approval.
    actors = [uuid4() for _ in range(8)]
    intent.operator_user_id, intent.review_by = actors[0], actors[1]
    approval = R(requested_by=actors[2], decided_by=actors[3])
    packet = R(id=values["packet"].id, packet_file_id=values["packet"].packet_file_id,
               created_by_user_id=actors[4])
    authorization.requested_by = actors[5]
    source = R(id=intent.source_file_id, company_id=tenant,
               payload=values["source_pdf"])
    intent.evidence_file_id = uuid4()
    evidence = R(id=intent.evidence_file_id, company_id=tenant,
                 payload=values["handwriting_png"])
    context = R(
        company_id=tenant, branch_id=None,
        staff=R(role=UserRole.COMPANY_ADMIN),
        user=R(id=actors[7]),
        is_platform_admin=False,
    )
    intent.document_version = "1"
    contract = R(
        id=intent.contract_id, company_id=tenant,
        borrower_id=intent.borrower_id, pdf_file_id=intent.source_file_id,
        version=1, status="draft", borrower_signed_at=None, locked_at=None,
    )
    state = {"receipt": None, "saved": None, "managed_calls": 0, "commits": 0}
    class Query:
        def __init__(self, model):
            self.model = model
        def filter(self, *clauses):
            return self
        def with_for_update(self):
            return self
        def one_or_none(self):
            if self.model is WacomExecutionAuthorization:
                return authorization
            if self.model is LoanContract:
                return contract
            if self.model is WacomExecutionReceipt:
                return state["receipt"]
            if self.model is ManagedFile:
                state["managed_calls"] += 1
                if state["managed_calls"] == 1:
                    return source
                if state["managed_calls"] == 2:
                    return evidence
                return state["saved"]
            raise AssertionError(f"unexpected query: {self.model}")
    class Db:
        def query(self, model):
            return Query(model)
        def add(self, row):
            if isinstance(row, WacomExecutionReceipt):
                state["receipt"] = row
        def commit(self):
            state["commits"] += 1
        def rollback(self):
            raise AssertionError("Valid archive unexpectedly rolled back")

    def store_bytes(_db, *, content, **kwargs):
        saved = R(
            id=uuid4(), company_id=tenant, payload=content,
            is_deleted=False, is_encrypted=True, is_confidential=True,
            scan_status="clean", mime_type="application/pdf",
            category="wacom_execution_candidate",
            checksum_sha256=sha256(content).hexdigest(),
        )
        state["saved"] = saved
        return saved

    monkeypatch.setattr(endpoint, "_locked_sources",
                        lambda *args: (approval, intent, packet))
    monkeypatch.setattr(endpoint, "_review_sources", lambda *args: None)
    monkeypatch.setattr(endpoint, "_confirm_packet", lambda *args: None)
    monkeypatch.setattr(endpoint, "store_bytes", store_bytes)
    monkeypatch.setattr(endpoint, "read_file_bytes", lambda file: file.payload)
    # Source preflight has its own tests, but is not the focus here.
    monkeypatch.setattr(endpoint, "reserve_execution_blockers", lambda **kwargs: [])
    # The final commit policy remains real, including PDF/field/hash checks.
    db = Db()
    first = endpoint.archive_pdf_candidate(
        authorization_id=authorization.id, response=Response(), db=db, ctx=context,
    )
    assert first["status"] == "candidate_archived_not_signed"
    assert first["duplicate"] is False
    assert first["contract_signed"] is False
    assert state["commits"] == 1
    assert state["receipt"].status == "reserved"
    assert state["receipt"].executed_at is None
    assert sha256(state["saved"].payload).hexdigest() == first["candidate_pdf_sha256"]
    # The real route must not create a second file or receipt on exact retry.
    again = endpoint.archive_pdf_candidate(
        authorization_id=authorization.id, response=Response(), db=db, ctx=context,
    )
    assert again["duplicate"] is True
    assert again["candidate_file_id"] == first["candidate_file_id"]
    assert state["commits"] == 1

def test_candidate_retry_rejects_changed_or_signed_contract():
    from fastapi import HTTPException
    from routers.wacom_pdf_candidates import _verify_existing
    values, _ = fixture()
    intent = values["intent"]
    intent.document_version = "1"
    contract = R(
        id=intent.contract_id, company_id=intent.company_id,
        borrower_id=intent.borrower_id, pdf_file_id=intent.source_file_id,
        version=1, status="draft", borrower_signed_at=None, locked_at=None,
    )
    ctx = R(company_id=intent.company_id)
    for field, changed in (
        ("status", "signed"),
        ("borrower_signed_at", datetime.now(timezone.utc)),
        ("version", 2),
        ("pdf_file_id", uuid4()),
        ("borrower_id", uuid4()),
        ("company_id", uuid4()),
    ):
        modified = R(**vars(contract))
        setattr(modified, field, changed)
        with pytest.raises(HTTPException) as exc:
            _verify_existing(None, ctx, R(), intent, values["execution_authorization"], modified)
        assert exc.value.status_code == 409
