"""Review PDF appendix must not turn a captured image into contract execution."""
from io import BytesIO
from hashlib import sha256

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services.wacom_pdf_evidence_package import build_review_evidence_pdf


def fixture():
    pdf = BytesIO()
    doc = canvas.Canvas(pdf)
    doc.drawString(72, 720, "Synthetic loan contract for Wacom tests")
    doc.save()
    png = BytesIO()
    Image.new("RGB", (160, 50), "white").save(png, format="PNG")
    original, ink = pdf.getvalue(), png.getvalue()
    return dict(
        source_pdf=original, source_sha256=sha256(original).hexdigest(),
        handwriting_png=ink, evidence_sha256=sha256(ink).hexdigest(),
        contract_id="contract-synthetic",
        intent_id="intent-synthetic",
        binding_sha256="c"*64,
        consent_reference="CONSENT-SYNTHETIC",
        review_reference="REVIEW-SYNTHETIC",
    )


def test_pdf_has_original_and_clearly_marked_evidence_appendix():
    values = fixture()
    result, checksum = build_review_evidence_pdf(**values)
    assert checksum == sha256(result).hexdigest()
    pdf = PdfReader(BytesIO(result))
    assert len(pdf.pages) == 2
    original_page = pdf.pages[0].extract_text()
    assert "Synthetic loan contract" in original_page
    appendix = pdf.pages[1].extract_text()
    assert "NOT SIGNED" in appendix
    assert values["consent_reference"] in appendix
    assert values["review_reference"] in appendix
    assert values["source_sha256"] in appendix
    assert "REVIEW PREVIEW" in appendix


@pytest.mark.parametrize("key,mutation", [
    ("source_pdf", b"%PDF-1.4\nfake altered content"),
    ("handwriting_png", b"broken image"),
    ("source_sha256", "a"*64),
    ("evidence_sha256", "b"*64),
])
def test_tampered_input_never_produces_a_pdf(key, mutation):
    values = fixture()
    values[key] = mutation
    with pytest.raises(HTTPException):
        build_review_evidence_pdf(**values)


def test_malformed_pdf_fails_closed_with_matching_digest():
    values = fixture()
    values["source_pdf"] = b"%PDF-1.4\nnot-a-real-document"
    values["source_sha256"] = sha256(values["source_pdf"]).hexdigest()
    with pytest.raises(HTTPException):
        build_review_evidence_pdf(**values)


def test_no_signature_is_written_into_source_document():
    values = fixture()
    result, _ = build_review_evidence_pdf(**values)
    output = PdfReader(BytesIO(result))
    assert len(output.pages) == 2
    assert "NOT SIGNED" not in output.pages[0].extract_text()
    assert output.metadata.title == "LoanHub reviewed Wacom evidence - NOT SIGNED"
