from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


_INSTALLED = False


def _folio(loan: Any) -> str | None:
    value = getattr(loan, "folio_number", None)
    text = str(value or "").strip().upper()
    return text or None


def stamp_pdf_folio(content: bytes, folio_number: str | None) -> bytes:
    """Stamp a permanent loan folio on every PDF page without changing its content stream."""
    if not content or not folio_number:
        return content
    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay_buffer = BytesIO()
        overlay = canvas.Canvas(overlay_buffer, pagesize=(width, height))
        overlay.saveState()
        overlay.setFillColor(colors.HexColor("#52606D"))
        overlay.setFont("Helvetica-Bold", 6.2)
        overlay.drawRightString(width - 4.5 * mm, 2.4 * mm, f"FOLIO {folio_number}")
        overlay.restoreState()
        overlay.save()
        overlay_buffer.seek(0)
        overlay_page = PdfReader(overlay_buffer).pages[0]
        page.merge_page(overlay_page)
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def install_folio_identity_integration() -> None:
    """Install folio propagation before API routers bind document functions.

    The folio is a loan identity. This hook deliberately does not create or mutate
    folio sequences; sequence allocation remains exclusively in services.loan_folio.
    It only makes an already-assigned folio visible in documents and snapshots.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    # Contract snapshots + every contract page (agreement, repayment annexure,
    # debit-order mandate and final signature annexure).
    from services import contract_service, contract_service_base

    contract_build_terms = contract_service.build_terms
    base_build_terms = contract_service_base.build_terms

    def enrich_terms(terms: dict[str, Any], loan: Any) -> dict[str, Any]:
        folio_number = _folio(loan)
        if not folio_number:
            return terms
        enriched = dict(terms)
        enriched["folio_number"] = folio_number
        enriched["folio_company_code"] = getattr(loan, "folio_company_code", None)
        enriched["folio_group_code"] = getattr(loan, "folio_group_code", None)
        enriched["folio_sequence"] = getattr(loan, "folio_sequence", None)
        return enriched

    def wrapped_contract_build_terms(db, loan):
        return enrich_terms(contract_build_terms(db, loan), loan)

    def wrapped_base_build_terms(db, loan):
        return enrich_terms(base_build_terms(db, loan), loan)

    contract_service.build_terms = wrapped_contract_build_terms
    contract_service_base.build_terms = wrapped_base_build_terms
    # Contract service delegates generation back through the base module.
    if getattr(contract_service, "_base", None) is not None:
        contract_service._base.build_terms = wrapped_contract_build_terms

    original_contract_branding = contract_service_base._ContractCanvas._draw_branding

    def draw_contract_branding_with_folio(self, page_count: int) -> None:
        original_contract_branding(self, page_count)
        terms = self.contract.terms_snapshot or {}
        folio_number = str(terms.get("folio_number") or "").strip().upper()
        if not folio_number:
            return
        width, height = self._pagesize
        self.saveState()
        self.setFillColor(contract_service_base.BLUE)
        self.setFont("Helvetica-Bold", 6.8)
        self.drawRightString(width - 18 * mm, height - 34.4 * mm, f"LOAN FOLIO: {folio_number}")
        self.restoreState()

    contract_service_base._ContractCanvas._draw_branding = draw_contract_branding_with_folio

    # Loan-generated A4 documents (repayment schedule, payment history,
    # settlement material and other loan documents) use DocumentContext.
    from services import loan_document_service
    from services.pdf_design_system import DocumentContext

    original_document_context = loan_document_service._document_context

    def folio_document_context(db, loan, title: str) -> DocumentContext:
        context = original_document_context(db, loan, title)
        folio_number = _folio(loan)
        if not folio_number:
            return context
        return DocumentContext(
            db=context.db,
            company=context.company,
            title=context.title,
            reference=f"Folio {folio_number} | Loan {loan.loan_reference}",
            footer_note=context.footer_note,
            confidential=context.confidential,
        )

    loan_document_service._document_context = folio_document_context

    # Thermal payment/disbursement slips retain their original layout. A small
    # non-invasive footer stamp ties every regenerated receipt to the loan book.
    from services import receipt_service

    original_receipt_pdf = receipt_service._pdf_bytes

    def receipt_pdf_with_folio(db, receipt, payment, loan):
        content = original_receipt_pdf(db, receipt, payment, loan)
        return stamp_pdf_folio(content, _folio(loan))

    receipt_service._pdf_bytes = receipt_pdf_with_folio

    # Collection case payloads expose the permanent folio beside the mutable
    # operational case and loan references.
    from routers import collections_recovery

    original_case_payload = collections_recovery._case_payload

    def case_payload_with_folio(db, case):
        payload = original_case_payload(db, case)
        if not payload.get("missing_loan"):
            loan = db.get(collections_recovery.ClientCompanyLoan, case.loan_id)
            payload["folio_number"] = _folio(loan)
            payload["folio_group_code"] = getattr(loan, "folio_group_code", None) if loan else None
        return payload

    collections_recovery._case_payload = case_payload_with_folio

    _INSTALLED = True
