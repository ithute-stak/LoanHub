"""Pure final PDF candidate tests: never establish execution or mutate contracts."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services.wacom_approved_field import bind_approved_field
from services.wacom_final_pdf_candidate import render_final_pdf_candidate


def sample():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.drawString(80, 730, "Source contract page 1")
    pdf.showPage()
    pdf.drawString(80, 730, "Source contract page 2")
    pdf.save()
    source = buffer.getvalue()
    image = Image.new("RGBA", (200, 70), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(10, 40), (80, 10), (170, 45)], width=5, fill=(0, 0, 0, 255))
    png = BytesIO()
    image.save(png, format="PNG")
    ink = png.getvalue()
    source_digest, ink_digest = sha256(source).hexdigest(), sha256(ink).hexdigest()
    field, binding = bind_approved_field(
        source_pdf=source, expected_sha256=source_digest,
        page_index=1, expected_page_count=2, x=150, y=140,
        width=240, height=70,
    )
    auth = R(
        status="approved", consumed_at=None, authorized_by=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        document_sha256=source_digest, evidence_sha256=ink_digest,
        field_binding_sha256=binding, field_page_index=field.page_index,
        field_page_count=field.page_count, field_x=field.x, field_y=field.y,
        field_width=field.width, field_height=field.height,
    )
    return dict(source_pdf=source, handwriting_png=ink, authorization=auth,
                expected_source_sha256=source_digest,
                expected_handwriting_sha256=ink_digest)


def render(values):
    return render_final_pdf_candidate(**values)


def test_renders_unexecuted_pdf_candidate_on_only_selected_page():
    values = sample()
    data, digest = render(values)
    assert digest == sha256(data).hexdigest()
    pdf = PdfReader(BytesIO(data))
    assert len(pdf.pages) == 2
    assert "Source contract page 1" in pdf.pages[0].extract_text()
    assert "Source contract page 2" in pdf.pages[1].extract_text()
    assert len(pdf.pages[0].images) == 0
    assert len(pdf.pages[1].images) >= 1
    assert "NOT proof of contract execution" in pdf.metadata.subject
    assert values["authorization"].consumed_at is None


@pytest.mark.parametrize("attribute,value", [
    ("status", "pending"),
    ("status", "consumed"),
    ("authorized_by", None),
    ("consumed_at", datetime.now(timezone.utc)),
    ("field_x", 151),
    ("field_binding_sha256", "a" * 64),
    ("evidence_sha256", "0" * 64),
])
def test_rejects_unapproved_or_modified_authorization(attribute, value):
    values = sample()
    setattr(values["authorization"], attribute, value)
    with pytest.raises(HTTPException) as exc:
        render(values)
    assert exc.value.status_code == 409


def test_rejects_expired_permit():
    values = sample()
    values["authorization"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(HTTPException) as exc:
        render(values)
    assert exc.value.status_code == 409


def test_rejects_changed_source_and_png_bytes():
    for attribute in ("source_pdf", "handwriting_png"):
        values = sample()
        values[attribute] += b"altered"
        with pytest.raises(HTTPException) as exc:
            render(values)
        assert exc.value.status_code == 409


def test_rejects_blank_opaque_png_even_when_hash_matches():
    values = sample()
    image = Image.new("RGBA", (200, 70), (255, 255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    values["handwriting_png"] = buffer.getvalue()
    values["expected_handwriting_sha256"] = sha256(buffer.getvalue()).hexdigest()
    values["authorization"].evidence_sha256 = values["expected_handwriting_sha256"]
    with pytest.raises(HTTPException) as exc:
        render(values)
    assert exc.value.status_code == 422


def test_renderer_does_not_persist_or_mark_signed():
    import inspect
    source = inspect.getsource(render_final_pdf_candidate)
    for forbidden in ("db.commit(", "store_bytes(", "borrower_signed_at =", "contract.status ="):
        assert forbidden not in source
