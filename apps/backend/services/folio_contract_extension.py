from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

import services.contract_service as _contract
import services.contract_service_base as _base


_original_build_terms = _base.build_terms
_original_key_value_table = _base._key_value_table
_original_draw_branding = _base._ContractCanvas._draw_branding


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


# Contract generation in contract_service delegates into contract_service_base at runtime,
# so replacing the shared extension points keeps one contract implementation and avoids
# duplicating the legal document renderer.
_base.build_terms = build_terms
_contract.build_terms = build_terms
_base._key_value_table = _key_value_table
_base._ContractCanvas._draw_branding = _draw_branding
