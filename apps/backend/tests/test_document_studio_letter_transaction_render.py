"""Fail closed when an approved source or SQL transaction changes during rendering."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from services.document_studio_letter_branding_evidence import capture_letter_branding_evidence
from services.document_studio_letter_render_evidence import RenderedLetterCandidate
from services.document_studio_letter_render_snapshot import letter_render_snapshot_sha256
from services.document_studio_letter_source_lock import LockedLetterSource
from services.document_studio_letter_stamp_authorization import AuthorizedLetterStamp
from services.document_studio_letter_transaction_render import render_authorized_letter_evidence


def scenario():
    tenant, doc_id = uuid4(), uuid4()
    document = SimpleNamespace(
        id=doc_id, company_id=tenant, template_key="formal_letter", version=2,
        content_html="<p>Company letter</p>", status="draft",
        finalized_at=None, is_deleted=False,
    )
    company = SimpleNamespace(
        id=tenant, name="Example Company", registration_number="REG-01",
        license_number=None, phone=None, email=None, website=None,
        address=None, district=None,
    )
    source = LockedLetterSource(
        tenant_id=tenant, document_id=doc_id, version=2,
        template_key="formal_letter",
        content_sha256=sha256(document.content_html.encode()).hexdigest(),
        render_snapshot_sha256=letter_render_snapshot_sha256(document),
    )
    approval = AuthorizedLetterStamp(
        tenant_id=tenant, configuration_version=1,
        stamp_snapshot_sha256="a" * 64, legal_name=company.name,
        approved_by_user_id=uuid4(), source=source,
    )
    pdf = b"%PDF-1.4\nCandidate PDF bytes"
    rendered = RenderedLetterCandidate(
        tenant_id=tenant, pdf_bytes=pdf,
        pdf_sha256=sha256(pdf).hexdigest(),
        header_branding=capture_letter_branding_evidence(
            document=document, company=company,
            left_logo=None, right_logo=None,
        ),
    )
    db = Mock()
    return db, document, company, tenant, approval, rendered


def invoke(db, document, company, tenant, approval, rendered, **patches):
    with patch(
        "services.document_studio_letter_transaction_render.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="12"),
    ), patch(
        "services.document_studio_letter_transaction_render.require_same_issuer_transaction",
    ) as guard, patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
        return_value=rendered, **patches,
    ) as renderer:
        result = render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=document,
            company=company, authenticated_tenant_id=tenant,
        )
        guard.assert_called_once()
        renderer.assert_called_once()
        return result


def test_matching_approval_source_pdf_and_transaction_produce_evidence():
    db, doc, company, tenant, approval, rendered = scenario()
    result = invoke(db, doc, company, tenant, approval, rendered)
    assert result.rendered_pdf_sha256 == sha256(rendered.pdf_bytes).hexdigest()
    assert result.header_branding_sha256 == rendered.header_branding.combined_sha256
    assert result.source_html_sha256 == approval.source.content_sha256
    assert result.approved_stamp_snapshot_sha256 == approval.stamp_snapshot_sha256
    db.commit.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize("tamper", ["tenant", "version", "source", "html", "layout"])
def test_stale_or_mismatched_source_fails_before_renderer(tamper):
    db, doc, company, tenant, approval, rendered = scenario()
    if tamper == "tenant":
        company.id = uuid4()
    elif tamper == "version":
        doc.version += 1
    elif tamper == "source":
        approval = replace(approval, source=replace(approval.source, document_id=uuid4()))
    elif tamper == "html":
        doc.content_html = "<p>Replaced content</p>"
    elif tamper == "layout":
        doc.margin_top_mm = 40
    with patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
    ) as renderer, pytest.raises(PermissionError):
        render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=doc,
            company=company, authenticated_tenant_id=tenant,
        )
    renderer.assert_not_called()


def test_replaced_sqlalchemy_transaction_during_rendering_rejected():
    db, doc, company, tenant, approval, rendered = scenario()
    db.get_transaction.side_effect = [object(), object()]
    with patch(
        "services.document_studio_letter_transaction_render.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="12"),
    ), patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
        return_value=rendered,
    ), pytest.raises(PermissionError, match="transaction replaced"):
        render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=doc,
            company=company, authenticated_tenant_id=tenant,
        )


def test_changed_postgres_transaction_during_rendering_rejected():
    db, doc, company, tenant, approval, rendered = scenario()
    with patch(
        "services.document_studio_letter_transaction_render.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="12"),
    ), patch(
        "services.document_studio_letter_transaction_render.require_same_issuer_transaction",
        side_effect=PermissionError("PostgreSQL issuer transaction changed"),
    ), patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
        return_value=rendered,
    ), pytest.raises(PermissionError, match="transaction changed"):
        render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=doc,
            company=company, authenticated_tenant_id=tenant,
        )


def test_changed_source_after_renderer_returns_is_rejected():
    db, doc, company, tenant, approval, rendered = scenario()
    def mutate(**kwargs):
        doc.content_html += "<p>Injected content</p>"
        return rendered
    with patch(
        "services.document_studio_letter_transaction_render.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="12"),
    ), patch(
        "services.document_studio_letter_transaction_render.require_same_issuer_transaction",
    ), patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
        side_effect=mutate,
    ), pytest.raises(PermissionError, match="changed during PDF rendering"):
        render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=doc,
            company=company, authenticated_tenant_id=tenant,
        )


def test_corrupt_renderer_hash_denied():
    db, doc, company, tenant, approval, rendered = scenario()
    corrupted = replace(rendered, pdf_sha256="f" * 64)
    with patch(
        "services.document_studio_letter_transaction_render.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="12"),
    ), patch(
        "services.document_studio_letter_transaction_render.render_letter_pdf_with_header_evidence",
        return_value=corrupted,
    ), pytest.raises(PermissionError, match="Renderer output"):
        render_authorized_letter_evidence(
            db=db, authorized_stamp=approval, document=doc,
            company=company, authenticated_tenant_id=tenant,
        )
