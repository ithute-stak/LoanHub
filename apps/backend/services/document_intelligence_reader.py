"""Bounded, read-only OCR entry point for LoanHub document intelligence.

Requires Poppler (pdfinfo, pdftoppm), Tesseract, Pillow and pypdf already
present in the backend runtime. No raw documents are persisted here; callers
must enforce authentication, tenant scoping, consent and retention policies.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from typing import Callable

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from services.document_intelligence_foundation import (
    DocumentKind,
    classify_document,
    orientation_candidates,
)

MAX_INPUT_BYTES = 12 * 1024 * 1024
MAX_PAGES = 10
MAX_PIXELS = 18_000_000
MAX_PAGE_SIDE = 5500
OCR_TIMEOUT_SECONDS = 25
PDF_RENDER_TIMEOUT_SECONDS = 45
SUPPORTED_IMAGES = {"PNG", "JPEG", "WEBP", "TIFF"}

# The caller never receives raw OCR logs with personal information.
class DocumentReadError(ValueError):
    pass


@dataclass(frozen=True)
class ReadPage:
    page_number: int
    text: str
    orientation_correction: int
    classification: DocumentKind
    confidence: float
    review_required: bool


@dataclass(frozen=True)
class ReadDocument:
    pages: tuple[ReadPage, ...]
    classification: DocumentKind
    review_required: bool
    full_text: str


def _run(args: list[str], *, input: bytes | None = None, timeout: int = OCR_TIMEOUT_SECONDS) -> bytes:
    try:
        result = subprocess.run(
            args, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise DocumentReadError("document processing utility unavailable or timed out") from exc
    if result.returncode:
        raise DocumentReadError("document processing utility failed")
    return result.stdout


def _safe_image(contents: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(contents)) as source:
            if source.format not in SUPPORTED_IMAGES:
                raise DocumentReadError("unsupported image format")
            if source.width * source.height > MAX_PIXELS:
                raise DocumentReadError("image exceeds pixel limit")
            if max(source.size) > MAX_PAGE_SIDE:
                raise DocumentReadError("image exceeds dimension limit")
            return ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise DocumentReadError("invalid image") from exc


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _ocr_tsv(image: Image.Image) -> tuple[str, float]:
    """TSV makes OCR confidence measurable without depending on guessed field values."""
    result = _run(
        ["tesseract", "stdin", "stdout", "--psm", "3", "tsv"],
        input=_png(image),
    ).decode("utf-8", errors="replace")
    words: list[str] = []
    confidences: list[float] = []
    for line in result.splitlines()[1:]:
        cols = line.split("\t", 11)
        if len(cols) != 12 or not cols[11].strip():
            continue
        try:
            confidence = float(cols[10])
        except ValueError:
            continue
        if 0 <= confidence <= 100:
            words.append(cols[11].strip())
            confidences.append(confidence)
    if not words:
        return "", 0.0
    return " ".join(words), sum(confidences) / len(confidences)


def _score(text: str, confidence: float) -> float:
    """Prioritise recognisable document anchors over plausible but wrong rotation."""
    lower = text.casefold()
    anchors = (
        "staff payslip", "total deductions", "net pay", "earnings",
        "opening balance", "closing balance", "transaction", "value date",
        "account number", "employee reference", "staff no",
    )
    anchor_count = sum(anchor in lower for anchor in anchors)
    return confidence + min(anchor_count, 7) * 12 + min(len(text), 500) / 100


def _read_image(image: Image.Image, page_number: int) -> ReadPage:
    results: list[tuple[float, float, int, str]] = []
    for correction in orientation_candidates():
        text, confidence = _ocr_tsv(image.rotate(correction, expand=True))
        results.append((_score(text, confidence), confidence, correction, text))
    results.sort(key=lambda result: result[0], reverse=True)
    _, confidence, correction, text = results[0]
    kind = classify_document(text)
    # Low confidence or unknown type must be reviewed; this is not issuer verification.
    review = confidence < 70 or kind == DocumentKind.UNKNOWN or len(text) < 50
    return ReadPage(page_number, text, correction, kind, round(confidence, 2), review)


def _pdf_pages(contents: bytes) -> list[tuple[str, Image.Image | str]]:
    """Extract native text or render scanned pages within strict resource bounds."""
    try:
        reader = PdfReader(BytesIO(contents), strict=True)
        if reader.is_encrypted:
            raise DocumentReadError("encrypted PDFs are not accepted")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise DocumentReadError("PDF page count outside permitted range")
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError("invalid PDF") from exc

    pages: list[tuple[str, Image.Image | str]] = []
    # Temp files are deleted before the function returns; no long-lived document copy.
    with TemporaryDirectory(prefix="loanhub-document-") as temp:
        source = Path(temp) / "source.pdf"
        source.write_bytes(contents)
        for number, page in enumerate(reader.pages, start=1):
            try:
                native_text = page.extract_text() or ""
            except Exception as exc:
                raise DocumentReadError("PDF text extraction failed") from exc
            if len(native_text.strip()) >= 90:
                pages.append(("text", native_text))
                continue
            prefix = Path(temp) / ("page" + str(number))
            _run(
                ["pdftoppm", "-f", str(number), "-l", str(number),
                 "-singlefile", "-scale-to", "2400", "-png", str(source), str(prefix)],
                timeout=PDF_RENDER_TIMEOUT_SECONDS,
            )
            raster = prefix.with_suffix(".png")
            if not raster.exists():
                raise DocumentReadError("PDF page rendering failed")
            pages.append(("image", _safe_image(raster.read_bytes())))
            raster.unlink()
    return pages


def read_document(contents: bytes, *, filename: str) -> ReadDocument:
    """Read provided bytes only, no filesystem paths/URLs supplied by the client.

    A caller must not use these results as a substitute for verified identity,
    issuer verification or an approved affordability assessment.
    """
    if not contents or len(contents) > MAX_INPUT_BYTES:
        raise DocumentReadError("document is empty or exceeds upload limit")
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        if not contents.startswith(b"%PDF-"):
            raise DocumentReadError("file extension does not match PDF content")
        source_pages = _pdf_pages(contents)
    elif extension in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        image = _safe_image(contents)
        source_pages = [("image", image)]
    else:
        raise DocumentReadError("unsupported document extension")
    results: list[ReadPage] = []
    for number, (mode, payload) in enumerate(source_pages, start=1):
        if mode == "text":
            extracted = str(payload)
            kind = classify_document(extracted)
            results.append(ReadPage(number, extracted, 0, kind, 100.0, kind == DocumentKind.UNKNOWN))
        else:
            results.append(_read_image(payload, number))  # type: ignore[arg-type]
    combined = "\n".join(page.text for page in results)
    kind = classify_document(combined)
    return ReadDocument(
        pages=tuple(results),
        classification=kind,
        review_required=any(page.review_required for page in results) or kind == DocumentKind.UNKNOWN,
        full_text=combined,
    )
