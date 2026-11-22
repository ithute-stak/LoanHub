"""Non-routed letter issuance adapter rejects provenance or transaction drift."""
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from core.access_control import TenantContext
from services.document_studio_letter_issuance_pipeline import issue_approved_company_letter_locked
from services.document_studio_letter_stamp_authorization import AuthorizedLetterStamp
from services.document_studio_letter_source_lock import LockedLetterSource
from services.document_studio_letter_render_snapshot import letter_render_snapshot_sha256
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore


def setup_case():
    tenant, issuer, doc_id = uuid4(), uuid4(), uuid4()
    company = SimpleNamespace(id=tenant, name="Example Finance")
    document = SimpleNamespace(
        id=doc_id, company_id=tenant, version=3,
        template_key="formal_letter", status="draft",
        finalized_at=None, content_html="<p>Approved company letter</p>",
    )
    context = TenantContext(
        user=SimpleNamespace(id=issuer),
        staff=SimpleNamespace(company_id=tenant, user_id=issuer),
        company=company, company_id=tenant,
        branch_id=None, is_platform_admin=False,
    )
    source = LockedLetterSource(
        tenant_id=tenant, document_id=doc_id, version=3,
        template_key="formal_letter",
        content_sha256=sha256(document.content_html.encode()).hexdigest(),
        render_snapshot_sha256=letter_render_snapshot_sha256(document),
    )
    approved = AuthorizedLetterStamp(
        tenant_id=tenant, source=source, configuration_version=2,
        approved_by_user_id=uuid4(), stamp_snapshot_sha256="b"*64,
        legal_name=company.name,
    )
    pdf = b"%PDF-1.4\nSource bytes"
    rendered = SimpleNamespace(
        tenant_id=tenant, document_id=doc_id, version=3,
        source_html_sha256=source.content_sha256,
        render_snapshot_sha256=source.render_snapshot_sha256,
        approved_stamp_snapshot_sha256=approved.stamp_snapshot_sha256,
        rendered_pdf_sha256=sha256(pdf).hexdigest(), pdf_bytes=pdf,
    )
    staged = SimpleNamespace(
        candidate=SimpleNamespace(tenant_id=tenant),
        source_sha256_hex=rendered.rendered_pdf_sha256,
        stamp_snapshot_sha256_hex=approved.stamp_snapshot_sha256,
    )
    db = Mock()
    store = Mock(spec=S3ObjectLockPdfStore)
    kwargs = dict(
        db=db, context=context, document=document, company=company,
        authenticated_tenant_id=tenant, issuer_user_id=issuer,
        configuration_version=2, store=store,
        verification_origin="https://verify.example.test",
        idempotency_key="letter-123",
    )
    return kwargs, approved, rendered, staged


def call_with_mocks(kwargs, approved, rendered, staged):
    with patch(
        "services.document_studio_letter_issuance_pipeline.preflight_approved_letter_stamp",
        return_value=approved,
    ) as preflight, patch(
        "services.document_studio_letter_issuance_pipeline.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=111, transaction_id="10"),
    ), patch(
        "services.document_studio_letter_issuance_pipeline.render_authorized_letter_evidence",
        return_value=rendered,
    ) as renderer, patch(
        "services.document_studio_letter_issuance_pipeline.stage_locked_document_candidate",
        return_value=staged,
    ) as stage, patch(
        "services.document_studio_letter_issuance_pipeline.require_same_issuer_transaction",
    ) as guard, patch(
        "services.document_studio_letter_issuance_pipeline.register_locked_staged_document",
        return_value=object(),
    ) as register:
        result = issue_approved_company_letter_locked(**kwargs)
        return result, preflight, renderer, stage, guard, register


def test_pipeline_connects_locked_letter_render_stage_and_registration():
    kwargs, approved, rendered, staged = setup_case()
    result, preflight, renderer, stage, guard, register = call_with_mocks(
        kwargs, approved, rendered, staged,
    )
    preflight.assert_called_once()
    renderer.assert_called_once()
    stage.assert_called_once()
    guard.assert_called_once()
    register.assert_called_once()
    assert register.call_args.kwargs["source_pdf"] == rendered.pdf_bytes
    assert register.call_args.kwargs["source_id"] == str(approved.source.document_id)
    assert register.call_args.kwargs["document_type"] == "formal_letter"
    kwargs["db"].commit.assert_not_called()


def test_cross_tenant_request_denied_before_side_effects():
    kwargs, approved, rendered, staged = setup_case()
    kwargs["authenticated_tenant_id"] = uuid4()
    with patch(
        "services.document_studio_letter_issuance_pipeline.preflight_approved_letter_stamp",
    ) as preflight, pytest.raises(PermissionError, match="Authenticated issuer"):
        issue_approved_company_letter_locked(**kwargs)
    preflight.assert_not_called()


@pytest.mark.parametrize("tamper", ["tenant", "source_pdf", "stamp"])
def test_staged_data_mismatch_aborts_before_commit(tamper):
    kwargs, approved, rendered, staged = setup_case()
    if tamper == "tenant":
        staged.candidate.tenant_id = uuid4()
    elif tamper == "source_pdf":
        staged.source_sha256_hex = "0"*64
    else:
        staged.stamp_snapshot_sha256_hex = "0"*64
    with patch(
        "services.document_studio_letter_issuance_pipeline.preflight_approved_letter_stamp",
        return_value=approved,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=1, transaction_id="1"),
    ), patch(
        "services.document_studio_letter_issuance_pipeline.render_authorized_letter_evidence",
        return_value=rendered,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.stage_locked_document_candidate",
        return_value=staged,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.register_locked_staged_document",
    ) as register, pytest.raises(PermissionError, match="Staged official letter"):
        issue_approved_company_letter_locked(**kwargs)
    register.assert_not_called()


def test_transaction_replacement_during_staging_denied_without_registration():
    kwargs, approved, rendered, staged = setup_case()
    kwargs["db"].get_transaction.side_effect = [object(), object()]
    with patch(
        "services.document_studio_letter_issuance_pipeline.preflight_approved_letter_stamp",
        return_value=approved,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=1, transaction_id="1"),
    ), patch(
        "services.document_studio_letter_issuance_pipeline.render_authorized_letter_evidence",
        return_value=rendered,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.stage_locked_document_candidate",
        return_value=staged,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.register_locked_staged_document",
    ) as register, pytest.raises(PermissionError, match="transaction changed"):
        issue_approved_company_letter_locked(**kwargs)
    register.assert_not_called()


def test_change_to_letter_after_staging_denied():
    kwargs, approved, rendered, staged = setup_case()
    def mutate(**arguments):
        kwargs["document"].content_html += "<p>Replaced</p>"
        return staged
    with patch(
        "services.document_studio_letter_issuance_pipeline.preflight_approved_letter_stamp",
        return_value=approved,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=1, transaction_id="1"),
    ), patch(
        "services.document_studio_letter_issuance_pipeline.render_authorized_letter_evidence",
        return_value=rendered,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.stage_locked_document_candidate",
        side_effect=mutate,
    ), patch(
        "services.document_studio_letter_issuance_pipeline.require_same_issuer_transaction",
    ), patch(
        "services.document_studio_letter_issuance_pipeline.register_locked_staged_document",
    ) as register, pytest.raises(PermissionError, match="changed during immutable"):
        issue_approved_company_letter_locked(**kwargs)
    register.assert_not_called()
