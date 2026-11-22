"""Rendering input snapshots catch non-body changes that affect PDFs."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.document_studio_letter_render_snapshot import letter_render_snapshot_sha256


def _letter():
    return SimpleNamespace(
        id=uuid4(), company_id=uuid4(), content_html="<p>Dear client</p>",
        template_key="formal_letter", version=2, page_size="A4",
        cover_page={"title": "Letter", "sections": ["one", "two"]},
        address_blocks=[{"label": "To", "text": "Maseru"}],
        margin_top_mm=28, brand_logo_asset_id=None,
    )


def test_snapshot_is_stable_for_same_document_inputs():
    doc = _letter()
    assert letter_render_snapshot_sha256(doc) == letter_render_snapshot_sha256(doc)


@pytest.mark.parametrize("field,value", [
    ("margin_top_mm", 52), ("page_size", "LETTER"),
    ("content_html", "<p>Changed body</p>"), ("brand_logo_asset_id", uuid4()),
    ("cover_page", {"title": "New title"}), ("address_blocks", []),
    ("template_key", "paid_up_letter"), ("version", 3),
])
def test_pdf_input_mutations_change_snapshot(field, value):
    doc = _letter()
    before = letter_render_snapshot_sha256(doc)
    setattr(doc, field, value)
    assert letter_render_snapshot_sha256(doc) != before


def test_snapshot_canonicalizes_dictionary_order():
    doc = _letter()
    before = letter_render_snapshot_sha256(doc)
    doc.cover_page = {"sections": ["one", "two"], "title": "Letter"}
    assert letter_render_snapshot_sha256(doc) == before


def test_incomplete_source_rejected():
    doc = _letter()
    doc.id = None
    with pytest.raises(PermissionError, match="Incomplete"):
        letter_render_snapshot_sha256(doc)


def test_noncanonical_object_in_layout_fails_closed():
    doc = _letter()
    doc.cover_page = {"nested": object()}
    with pytest.raises(PermissionError, match="Unsupported"):
        letter_render_snapshot_sha256(doc)
