"""Exact-byte PDF evidence cannot cross letters or silently survive mutation."""
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4
from types import SimpleNamespace

import pytest

from services.document_studio_letter_pdf_binding import bind_letter_pdf_candidate
from services.document_studio_letter_source_lock import LockedLetterSource
from services.document_studio_letter_branding_evidence import capture_letter_branding_evidence
from services.document_issuance_integrity import pdf_fingerprint


def case():
    tenant, document_id = uuid4(), uuid4()
    digest = sha256(b"<p>Original letter</p>").hexdigest()
    snapshot = sha256(b"render settings").hexdigest()
    locked = LockedLetterSource(
        tenant_id=tenant, document_id=document_id,
        version=3, template_key="formal_letter", content_sha256=digest,
        render_snapshot_sha256=snapshot,
    )
    branding = capture_letter_branding_evidence(
        document=SimpleNamespace(company_id=tenant),
        company=SimpleNamespace(id=tenant, name="Example Finance",
            registration_number="REG", license_number="LIC",
            phone="+266 50000000", email="office@example.test",
            address="Maseru", website=None, district=None),
        left_logo=b"left-image-bytes", right_logo=b"right-image-bytes",
    )
    kwargs = dict(
        branding_evidence=branding,
        locked_source=locked, tenant_id=tenant, document_id=document_id,
        document_version=3, expected_source_html_sha256=digest,
        expected_render_snapshot_sha256=snapshot,
        source_pdf=b"%PDF-1.4\nOriginal preview bytes",
        candidate_pdf=b"%PDF-1.4\nStamped candidate bytes",
    )
    return kwargs


def test_exact_bytes_bound_to_locked_letter_evidence():
    kwargs = case()
    proof = bind_letter_pdf_candidate(**kwargs)
    assert proof.document_id == kwargs["document_id"]
    assert proof.document_version == 3
    assert proof.branding_sha256 == kwargs["branding_evidence"].combined_sha256
    assert proof.render_snapshot_sha256 == kwargs["expected_render_snapshot_sha256"]
    assert proof.rendered_source_pdf_sha256 == pdf_fingerprint(kwargs["source_pdf"])
    assert proof.candidate_pdf_sha256 == pdf_fingerprint(kwargs["candidate_pdf"])
    assert proof.rendered_source_pdf_sha256 != proof.candidate_pdf_sha256


@pytest.mark.parametrize("change", [
    {"tenant_id": uuid4()}, {"document_id": uuid4()},
    {"document_version": 4}, {"document_version": True},
    {"expected_source_html_sha256": "0" * 64},
    {"expected_source_html_sha256": None},
    {"expected_render_snapshot_sha256": "f" * 64},
    {"expected_render_snapshot_sha256": None},
    {"branding_evidence": None},
])
def test_mismatched_source_identity_or_content_denied(change):
    kwargs = case()
    kwargs.update(change)
    with pytest.raises(PermissionError):
        bind_letter_pdf_candidate(**kwargs)


@pytest.mark.parametrize("field", ["source_pdf", "candidate_pdf"])
def test_non_pdf_bytes_denied(field):
    kwargs = case()
    kwargs[field] = b"not a PDF"
    with pytest.raises(ValueError, match="Invalid finalized PDF"):
        bind_letter_pdf_candidate(**kwargs)


def test_candidate_mutation_changes_exact_byte_fingerprint():
    kwargs = case()
    before = bind_letter_pdf_candidate(**kwargs)
    kwargs["candidate_pdf"] += b"\nmodified"
    after = bind_letter_pdf_candidate(**kwargs)
    assert before.candidate_pdf_sha256 != after.candidate_pdf_sha256


def test_source_object_not_mutated_by_binding():
    kwargs = case()
    original = kwargs["locked_source"]
    bind_letter_pdf_candidate(**kwargs)
    assert kwargs["locked_source"] == original


def test_cross_tenant_branding_evidence_denied():
    kwargs = case()
    from dataclasses import replace
    kwargs["branding_evidence"] = replace(
        kwargs["branding_evidence"], tenant_id=uuid4(),
    )
    with pytest.raises(PermissionError, match="branding evidence"):
        bind_letter_pdf_candidate(**kwargs)
