from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

import services.contract_service as _contract
import services.contract_service_base as _base
import services.loan_document_service as _loan_documents
import services.receipt_service as _receipts


_original_build_terms = _base.build_terms
_original_key_value_table = _base._key_value_table
_original_draw_branding = _base._ContractCanvas._draw_branding
_original_loan_information_pdf = _loan_documents.generate_loan_information_pdf
_original_repayment_schedule_pdf = _loan_documents.generate_repayment_schedule_pdf
_original_payment_history_pdf = _loan_documents.generate_payment_history_pdf
_original_receipt_pdf_bytes = _receipts._pdf_bytes


def build_terms(db: Session, loan: Any) -> dict[str, Any]:
    """Freeze the immutable loan folio into every newly generated contract snapshot."""
    terms = dict(_original_build_terms(db, loan))
    terms["folio_number"] = getattr(loan, "folio_number", None)
    terms["folio_company_code"] = getattr(loan, "folio_company_code", None)
    terms["folio_group_code"] = getattr(loan, "folio_group_code", None)
    terms["folio_sequence"] = getattr(loan, "folio_sequence", None)
    return terms


def _key_value_table(rows: list[tuple[str, Any]], styles: dict[str, Any], **kwargs: Any):
    """Put Folio Number beside the agreement identity on the contract cover."""
    labels = [str(label).strip().lower() for label, _ in rows]
    if "agreement number" in labels and "folio number" not in labels:
        terms = _contract._active_contract_terms.get()
        folio = str(terms.get("folio_number") or "").strip()
        if folio:
            rows = list(rows)
            insert_at = 1 if rows else 0
            rows.insert(insert_at, ("Folio number", folio))
    return _original_key_value_table(rows, styles, **kwargs)


def _draw_branding(self: Any, page_count: int) -> None:
    """Stamp the permanent folio on every contract page without altering old signed terms."""
    _original_draw_branding(self, page_count)
    loan = getattr(self.contract, "loan", None)
    folio = str(getattr(loan, "folio_number", "") or "").strip()
    if not folio:
        terms = self.contract.terms_snapshot if isinstance(self.contract.terms_snapshot, dict) else {}
        folio = str(terms.get("folio_number") or "").strip()
    if not folio:
        return

    loan_reference = str(getattr(loan, "loan_reference", "") or "").strip()
    self.saveState()
    self.setFillColor(_base.BLUE)
    self.setFont("Helvetica-Bold", 6.5)
    identity = f"FOLIO {folio}"
    if loan_reference:
        identity += f" | LOAN {loan_reference}"
    self.drawCentredString(_base.A4[0] / 2, 16.7 * _base.mm, identity[:110])
    self.restoreState()


@contextmanager
def _folio_render_reference(loan: Any) -> Iterator[None]:
    """Expose folio + technical loan reference to existing PDF renderers, render-only.

    The SQLAlchemy value is changed with set_committed_value and restored immediately,
    so generating a PDF never schedules a database update or changes the stored loan number.
    """
    if loan is None:
        yield
        return
    original = str(getattr(loan, "loan_reference", "") or "").strip()
    folio = str(getattr(loan, "folio_number", "") or "").strip()
    if not folio or not original:
        yield
        return

    combined = f"{folio} | Loan {original}"
    set_committed_value(loan, "loan_reference", combined)
    try:
        yield
    finally:
        set_committed_value(loan, "loan_reference", original)


def generate_loan_information_pdf(db: Session, loan: Any) -> bytes:
    with _folio_render_reference(loan):
        return _original_loan_information_pdf(db, loan)


def generate_repayment_schedule_pdf(db: Session, loan: Any) -> bytes:
    with _folio_render_reference(loan):
        return _original_repayment_schedule_pdf(db, loan)


def generate_payment_history_pdf(db: Session, loan: Any) -> bytes:
    with _folio_render_reference(loan):
        return _original_payment_history_pdf(db, loan)


def _receipt_pdf_bytes(db: Session, receipt: Any, payment: Any, loan: Any) -> bytes:
    with _folio_render_reference(loan):
        return _original_receipt_pdf_bytes(db, receipt, payment, loan)


# Contract generation in contract_service delegates into contract_service_base at runtime,
# so replacing these shared extension points keeps one legal/document implementation while
# making the immutable folio visible throughout LoanHub's loan-document family.
_base.build_terms = build_terms
_contract.build_terms = build_terms
_base._key_value_table = _key_value_table
_base._ContractCanvas._draw_branding = _draw_branding
_loan_documents.generate_loan_information_pdf = generate_loan_information_pdf
_loan_documents.generate_repayment_schedule_pdf = generate_repayment_schedule_pdf
_loan_documents.generate_payment_history_pdf = generate_payment_history_pdf
_receipts._pdf_bytes = _receipt_pdf_bytes
