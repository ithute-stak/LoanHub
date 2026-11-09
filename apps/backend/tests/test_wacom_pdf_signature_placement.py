"""Watermarked Wacom signing-placement candidate tests using synthetic files."""
from io import BytesIO
from hashlib import sha256

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services.wacom_pdf_signature_placement import (
    SignatureField, STAMP, render_signature_placement_preview,
)


def sample():
    pdf = BytesIO()
    doc = canvas.Canvas(pdf, pagesize=(612, 792))
    doc.drawString(70, 740, "Synthetic contract: page one")
    doc.showPage()
    doc.drawString(70, 740, "Synthetic contract: page two")
    doc.save()
    png = BytesIO()
    image = Image.new("RGBA", (300, 80), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.line(((20, 45), (120, 20), (200, 50), (280, 10)), fill=(0, 0, 0, 255), width=4)
    image.save(png, format="PNG")
    original, ink = pdf.getvalue(), png.getvalue()
    return dict(
        source_pdf=original, source_sha256=sha256(original).hexdigest(),
        handwriting_png=ink, handwriting_sha256=sha256(ink).hexdigest(),
        expected_page_count=2,
        field=SignatureField(page_index=1, x=160, y=140, width=250, height=65),
    )


def test_preview_inserts_into_only_selected_page_with_clear_watermark():
    values=sample()
    result,digest=render_signature_placement_preview(**values)
    assert digest == sha256(result).hexdigest()
    preview=PdfReader(BytesIO(result))
    assert len(preview.pages)==2
    assert "Synthetic contract: page one" in preview.pages[0].extract_text()
    assert "Synthetic contract: page two" in preview.pages[1].extract_text()
    assert all(STAMP in page.extract_text() for page in preview.pages)
    assert preview.metadata.title.endswith("NOT EXECUTED")
    assert len(preview.pages[0].images) == 0
    assert len(preview.pages[1].images) >= 1


@pytest.mark.parametrize("field",[
    SignatureField(page_index=-1,x=50,y=50,width=200,height=80),
    SignatureField(page_index=2,x=50,y=50,width=200,height=80),
    SignatureField(page_index=1,x=-1,y=50,width=200,height=80),
    SignatureField(page_index=1,x=600,y=50,width=200,height=80),
    SignatureField(page_index=1,x=50,y=50,width=10,height=10),
    SignatureField(page_index=1,x=50,y=50,width=400,height=80),
    SignatureField(page_index=1,x=50,y=50,width=float("nan"),height=80),
])
def test_unauthorized_or_out_of_bounds_fields_rejected(field):
    values=sample()
    values["field"]=field
    with pytest.raises(HTTPException):
        render_signature_placement_preview(**values)


def test_changed_contract_does_not_render():
    values=sample()
    values["source_pdf"]+=b"post-consent mutation"
    with pytest.raises(HTTPException) as exc:
        render_signature_placement_preview(**values)
    assert exc.value.status_code == 409


def test_changed_handwriting_does_not_render():
    values=sample()
    values["handwriting_png"]+=b"altered"
    with pytest.raises(HTTPException) as exc:
        render_signature_placement_preview(**values)
    assert exc.value.status_code == 409


def test_wrong_page_count_rejected():
    values=sample()
    values["expected_page_count"]=1
    with pytest.raises(HTTPException):
        render_signature_placement_preview(**values)


def test_no_persistence_or_contract_mutation_in_renderer():
    import inspect
    src=inspect.getsource(render_signature_placement_preview)
    for forbidden in ("db.commit(", "store_bytes(", "borrower_signed_at =", "company_signed_at ="):
        assert forbidden not in src
