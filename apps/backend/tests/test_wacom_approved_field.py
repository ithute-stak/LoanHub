"""Signature-field authorization must bind a specific page and contract PDF."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from hashlib import sha256

from services.wacom_approved_field import bind_approved_field, stored_field_matches


def sample():
    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=(612, 792))
    doc.drawString(60, 740, "Synthetic contract first page")
    doc.showPage()
    doc.drawString(60, 740, "Synthetic contract signing page")
    doc.save()
    pdf = buffer.getvalue()
    args = dict(
        source_pdf=pdf, expected_sha256=sha256(pdf).hexdigest(),
        page_index=1, expected_page_count=2,
        x=160, y=140, width=250, height=65,
    )
    return args


def test_exact_field_hash_is_stable():
    args = sample()
    field, digest = bind_approved_field(**args)
    assert field.page_index == 1
    assert len(digest) == 64
    _, digest_again = bind_approved_field(**args)
    assert digest == digest_again


@pytest.mark.parametrize("attribute,value", [
    ("page_index", 0),
    ("x", 120),
    ("y", 170),
    ("width", 240),
    ("height", 80),
])
def test_changing_field_changes_digest(attribute, value):
    args = sample()
    _, original = bind_approved_field(**args)
    args[attribute] = value
    _, changed = bind_approved_field(**args)
    assert original != changed


@pytest.mark.parametrize("attribute,value", [
    ("page_index", -1),
    ("page_index", 2),
    ("page_index", True),
    ("x", -10),
    ("x", float("nan")),
    ("x", 100.0001),
    ("width", 0),
    ("width", 400),
    ("height", 151),
    ("page_count", 1),
])
def test_bad_fields_or_page_count_rejected(attribute, value):
    args = sample()
    args[attribute] = value
    with pytest.raises(ValueError):
        bind_approved_field(**args)


def test_modified_pdf_rejected():
    args = sample()
    args["source_pdf"] += b"modified"
    with pytest.raises(ValueError):
        bind_approved_field(**args)


def test_malformed_pdf_rejected():
    args = sample()
    args["source_pdf"] = b"%PDF-not a valid document"
    args["expected_sha256"] = sha256(args["source_pdf"]).hexdigest()
    with pytest.raises((ValueError, Exception)):
        bind_approved_field(**args)


def test_stored_bound_field_matches_and_legacy_null_fails_closed():
    args = sample()
    field, digest = bind_approved_field(**args)
    record = SimpleNamespace(
        field_page_index=field.page_index,
        field_page_count=field.page_count,
        field_x=field.x, field_y=field.y,
        field_width=field.width, field_height=field.height,
        field_binding_sha256=digest,
    )
    assert stored_field_matches(
        authorization=record, source_pdf=args["source_pdf"],
        expected_sha256=args["expected_sha256"],
    )
    record.field_x += 10
    assert not stored_field_matches(
        authorization=record, source_pdf=args["source_pdf"],
        expected_sha256=args["expected_sha256"],
    )
    assert not stored_field_matches(
        authorization=SimpleNamespace(), source_pdf=args["source_pdf"],
        expected_sha256=args["expected_sha256"],
    )


def test_invalid_source_size_and_hash():
    args = sample()
    args["expected_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        bind_approved_field(**args)
