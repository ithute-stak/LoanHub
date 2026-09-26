from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy.orm import Session

import services.contract_service_base as _base
from database.models.origination import LoanContract, OriginationIntegrationConfiguration
from services.contract_service_base import *  # noqa: F401,F403
from services.debit_order_mandate import build_debit_order_mandate
from services.lelefa_managed_collections import (
    PROVIDER,
    collection_charge_disclosure,
    normalize_collection_charge_policy,
)


EXPLICIT_COLLECTION_TEMPLATE_VERSION = "3.2-explicit-collection-cost-basis"
MANDATE_SIGNATURE_MODE = "single_contract_signature"

_original_build_terms = _base.build_terms
_original_contract_pdf = _base._contract_pdf
_original_generate_contract = _base.generate_contract
_original_clause = _base._clause
_original_cost_elements_table = _base._cost_elements_table
_original_simple_doc_template = _base.SimpleDocTemplate
_active_contract_terms: ContextVar[dict[str, Any]] = ContextVar(
    "active_contract_terms",
    default={},
)
_active_contract_reference: ContextVar[str] = ContextVar(
    "active_contract_reference",
    default="",
)
_active_include_mandate: ContextVar[bool] = ContextVar(
    "active_include_mandate",
    default=False,
)


def _company_collection_charge_policy(
    db: Session,
    company_id: Any,
) -> dict[str, Any]:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == PROVIDER,
        )
        .one_or_none()
    )
    return normalize_collection_charge_policy(row.configuration if row else None)


def build_terms(db: Session, loan: Any) -> dict[str, Any]:
    """Freeze collection policy and contract-generation choices into a new agreement.

    Existing contracts are deliberately left untouched. This prevents a later company
    setting, wording revision, or optional mandate choice from being injected into an
    agreement that was already generated for the borrower.
    """
    terms = _original_build_terms(db, loan)
    existing_contract = (
        db.query(LoanContract)
        .filter(LoanContract.loan_id == loan.id)
        .first()
    )
    if existing_contract is not None:
        return terms

    include_mandate = bool(_active_include_mandate.get())
    terms = dict(terms)
    terms["template_version"] = EXPLICIT_COLLECTION_TEMPLATE_VERSION
    terms["collection_charge"] = _company_collection_charge_policy(db, loan.company_id)
    terms["include_mandate"] = include_mandate
    terms["mandate_signature_mode"] = MANDATE_SIGNATURE_MODE if include_mandate else "not_included"
    return terms


def generate_contract(
    db: Session,
    *,
    loan: Any,
    requested_by_user_id: Any,
    witness_name: str | None = None,
    template_style: str = _base.CONTRACT_STYLE_STANDARD,
    include_mandate: bool = False,
) -> LoanContract:
    """Generate one agreement and freeze whether its debit-order mandate is included."""
    token = _active_include_mandate.set(bool(include_mandate))
    try:
        return _original_generate_contract(
            db,
            loan=loan,
            requested_by_user_id=requested_by_user_id,
            witness_name=witness_name,
            template_style=template_style,
        )
    finally:
        _active_include_mandate.reset(token)


def _collection_charge_cost_table(
    terms: dict[str, Any],
    styles: dict[str, Any],
) -> Any:
    policy = normalize_collection_charge_policy(
        {"collection_charge": terms.get("collection_charge") or {}}
    )
    template_version = str(terms.get("template_version") or "")
    if not policy["enabled"] and template_version != EXPLICIT_COLLECTION_TEMPLATE_VERSION:
        return _original_cost_elements_table(terms, styles)

    commission_disclosure = (
        collection_charge_disclosure(policy)
        if policy["enabled"]
        else (
            "No separate percentage-based or fixed collection commission is agreed under "
            "this agreement. Clause 11 separately addresses lawful external recovery and legal costs."
        )
    )
    processing_fee = _base._as_decimal(terms.get("processing_fee"))
    total_fees = _base._as_decimal(terms.get("total_fees"))
    other_fees = max(total_fees - processing_fee, _base.Decimal("0"))
    rows = [
        ["2.1 Amount of interest charged", _base._money(terms.get("total_interest"))],
        ["2.2 Initiation / processing fee", _base._money(processing_fee)],
        ["2.3 Other service and schedule fees", _base._money(other_fees)],
        ["2.4 Taxes included in disclosed charges", _base._money(terms.get("tax_amount"))],
        ["2.5 Conditional collection commission", commission_disclosure],
        [
            "2.6 Total charge of credit [2.1 to 2.4]",
            _base._money(terms.get("total_cost_of_credit")),
        ],
        ["3. Approved interest rate", _base._percentage(terms.get("interest_rate"))],
        [
            "4. Total amount added to the loan amount",
            _base._money(terms.get("total_cost_of_credit")),
        ],
        [
            "5. Total amount repayable [1.1 + 4]",
            _base._money(terms.get("total_repayable")),
        ],
    ]
    data = [
        [
            _base._p(label, styles["table_label"]),
            _base._p(value, styles["table_value"]),
        ]
        for label, value in rows
    ]
    table = _base.Table(data, colWidths=[132 * _base.mm, 42 * _base.mm])
    table.setStyle(_base.TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.55, _base.BORDER),
        ("BACKGROUND", (0, 4), (-1, 4), _base.WARNING),
        ("BACKGROUND", (0, 5), (-1, 5), _base.PALE_BLUE),
        ("BACKGROUND", (0, 7), (-1, -1), _base.PALE_TEAL),
        ("ALIGN", (1, 0), (1, 3), "RIGHT"),
        ("ALIGN", (1, 5), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _explicit_collection_clause(
    styles: dict[str, Any],
    policy: dict[str, Any],
) -> list[Any]:
    """Render the signed contractual basis for collection and recovery costs."""
    elements = _original_clause(
        "11",
        "Default, debt collection and recovery costs",
        (
            "If the borrower fails to pay an amount when due, does not remedy the default "
            "after any notice or opportunity required by applicable law, and the lender "
            "engages a lawfully authorised debt collector, attorney or other external recovery "
            "representative to recover amounts due under this agreement, the borrower expressly "
            "agrees to pay the lawful and reasonable external debt-collection and recovery costs "
            "actually incurred by the lender in recovering the debt, together with legal costs "
            "recoverable under applicable law or a competent court order. This clause is the "
            "parties' express contractual agreement that those qualifying recovery costs are for "
            "the borrower's account. No collection or legal charge becomes due merely because an "
            "instalment is late; every amount must be properly incurred or lawfully assessable, "
            "separately itemised, and permitted by applicable law."
        ),
        styles,
    )

    if policy["enabled"]:
        disclosure = collection_charge_disclosure(policy)
        elements.extend(
            _original_clause(
                "11.1",
                "Agreed collection commission after external referral",
                (
                    "In addition to the qualifying recovery costs described in clause 11, the "
                    "borrower expressly agrees to pay the following collection commission if the "
                    "stated arrears threshold is met and the account is actually referred for "
                    f"external debt collection: {disclosure} This commission is conditional, is "
                    "not part of the ordinary cost of credit or scheduled instalments, must be "
                    "separately shown on the borrower's account, and is payable only to the extent "
                    "permitted by applicable law."
                ),
                styles,
            )
        )
    else:
        elements.extend(
            _original_clause(
                "11.1",
                "Separate collection commission",
                (
                    "No separate percentage-based or fixed collection commission is agreed under "
                    "this agreement. Clause 11 still records the borrower's responsibility for "
                    "lawful and reasonable external debt-collection, recovery and legal costs "
                    "actually incurred or otherwise recoverable under applicable law."
                ),
                styles,
            )
        )
    return elements


def _mandate_contract_clause(
    number: str,
    heading: str,
    styles: dict[str, Any],
) -> list[Any] | None:
    if number == "10":
        return _original_clause(
            number,
            heading,
            (
                "The borrower agrees to repay the loan using an approved payment method. Where the "
                "Authority to Debit Account is included in this agreement, it is incorporated into and "
                "forms part of this contract. The borrower's single signature in the final Acceptance and "
                "Signatures section authorises both this credit agreement and the included debit-order "
                "mandate; LoanHub does not require a second signature on the mandate page. A failed "
                "third-party collection does not remove the borrower's obligation to pay by the due date."
            ),
            styles,
        )
    if number == "14":
        return _original_clause(
            number,
            heading,
            (
                "The borrower and lender agree that their rights and obligations are governed by this "
                "agreement, its incorporated annexures, including any Authority to Debit Account shown "
                "before the signature section, and the mandatory requirements of the laws of the Kingdom "
                "of Lesotho. The final agreement signature applies to the complete contract and every "
                "incorporated annexure. A contractual term cannot remove a right that the law makes non-waivable."
            ),
            styles,
        )
    if number == "19.3":
        return _original_clause(
            number,
            heading,
            (
                "This agreement, its cost disclosure, repayment schedule and every incorporated annexure "
                "appearing before the Acceptance and Signatures section form one complete agreement. The "
                "borrower's signature in that final section applies to all of them, including an Authority "
                "to Debit Account when present. Amendments must be written and lawfully accepted. If a clause "
                "is invalid, the remaining lawful clauses continue to apply."
            ),
            styles,
        )
    return None


def _collection_clause(
    number: str,
    heading: str,
    text: str,
    styles: dict[str, Any],
) -> list[Any]:
    terms = _active_contract_terms.get()
    template_version = str(terms.get("template_version") or "")
    policy = normalize_collection_charge_policy(
        {"collection_charge": terms.get("collection_charge") or {}}
    )

    if bool(terms.get("include_mandate")):
        mandate_clause = _mandate_contract_clause(number, heading, styles)
        if mandate_clause is not None:
            return mandate_clause

    if template_version == EXPLICIT_COLLECTION_TEMPLATE_VERSION:
        if number == "11":
            return _explicit_collection_clause(styles, policy)
        return _original_clause(number, heading, text, styles)

    elements = _original_clause(number, heading, text, styles)
    if number != "12" or not policy["enabled"]:
        return elements

    disclosure = collection_charge_disclosure(policy)
    elements.extend(
        _original_clause(
            "12.1",
            "Collection and recovery costs after qualifying default",
            (
                "If the borrower fails to remedy a payment default and the account reaches "
                f"the agreed arrears threshold, the borrower expressly agrees, to the extent "
                f"permitted by applicable law, to the following conditional collection charge: "
                f"{disclosure} The charge arises only when the account is actually referred for "
                "external debt collection or comparable external recovery action. It is separate "
                "from principal, contractual interest, ordinary administration/default charges "
                "and legal or court costs, must be separately shown on the account, and may not "
                "be imposed unless this signed agreement expressly authorises it."
            ),
            styles,
        )
    )
    return elements


def _plain_text(flowable: Any) -> str:
    if isinstance(flowable, _base.Paragraph):
        return flowable.getPlainText().strip()
    return ""


def _mark_payment_mandate_included(flowable: Any) -> None:
    if not isinstance(flowable, _base.Table):
        return

    cells = getattr(flowable, "_cellvalues", None)
    if not isinstance(cells, list):
        return

    if len(cells) >= 2 and cells[0] and cells[1]:
        label = cells[0][0]
        value = cells[1][0]
        if _plain_text(label) == "PAYMENT MANDATE ANNEXED":
            cells[0][0] = _base.Paragraph("PAYMENT MANDATE", label.style)
            value_style = value.style if isinstance(value, _base.Paragraph) else _base._styles()["table_value"]
            cells[1][0] = _base.Paragraph(
                "Included in this agreement - accepted by the borrower signature above",
                value_style,
            )

    for row in cells:
        if not isinstance(row, (list, tuple)):
            continue
        for cell in row:
            if isinstance(cell, _base.Table):
                _mark_payment_mandate_included(cell)
            elif isinstance(cell, (list, tuple)):
                for item in cell:
                    if isinstance(item, _base.Table):
                        _mark_payment_mandate_included(item)


def _integrate_single_signature_mandate(
    flowables: list[Any],
    terms: dict[str, Any],
    *,
    agreement_reference: str,
) -> None:
    signature_heading_index: int | None = None

    for index, flowable in enumerate(flowables):
        text = _plain_text(flowable)
        if text == "ANNEXURE B - ACCEPTANCE AND SIGNATURES":
            signature_heading_index = index
            flowables[index] = _base.Paragraph(
                "ANNEXURE C - ACCEPTANCE AND SIGNATURES",
                flowable.style,
            )
        elif text.startswith("By signing, the borrower confirms"):
            flowables[index] = _base.Paragraph(
                (
                    "By signing once below, the borrower accepts this entire credit agreement and every "
                    "incorporated annexure appearing before this signature section. <b>If Annexure B - "
                    "Authority to Debit Account is present, this same borrower signature also gives the "
                    "debit-order authority and mandate set out there; no second LoanHub mandate signature "
                    "is required.</b> The borrower further confirms that the loan amount, interest, fees, "
                    "total repayable, repayment dates, default consequences, payment arrangements and "
                    "complaint process were disclosed and explained; the supplied personal and financial "
                    "information is truthful; and a completed copy of the agreement will be provided or "
                    "made securely available."
                ),
                flowable.style,
            )

    if signature_heading_index is None:
        raise RuntimeError("LoanHub contract signature section was not found while inserting the debit-order mandate")

    bank = terms.get("bank_account") if isinstance(terms.get("bank_account"), dict) else None
    account_number = _base._bank_account_number(bank)
    insert_at = signature_heading_index
    if insert_at > 0 and isinstance(flowables[insert_at - 1], _base.PageBreak):
        insert_at -= 1

    mandate_flowables = build_debit_order_mandate(
        terms,
        agreement_reference=agreement_reference or str(terms.get("loan_reference") or ""),
        account_number=account_number,
    )
    flowables[insert_at:insert_at] = mandate_flowables

    for flowable in flowables:
        _mark_payment_mandate_included(flowable)


class _MandateAwareSimpleDocTemplate(_original_simple_doc_template):
    """Place an included mandate before the one final contract signature section."""

    def build(self, flowables: list[Any], *args: Any, **kwargs: Any) -> Any:
        terms = _active_contract_terms.get()
        if bool(terms.get("include_mandate")):
            _integrate_single_signature_mandate(
                flowables,
                terms,
                agreement_reference=_active_contract_reference.get(),
            )
        return super().build(flowables, *args, **kwargs)


def _contract_pdf(db: Session, contract: LoanContract) -> bytes:
    token = _active_contract_terms.set(
        contract.terms_snapshot if isinstance(contract.terms_snapshot, dict) else {}
    )
    reference_token = _active_contract_reference.set(str(contract.contract_number or ""))
    try:
        return _original_contract_pdf(db, contract)
    finally:
        _active_contract_reference.reset(reference_token)
        _active_contract_terms.reset(token)


# Keep the original rendering implementation intact while replacing only the narrow
# extension points needed for collection-charge controls and the optional debit mandate.
_base.build_terms = build_terms
_base.generate_contract = generate_contract
_base._cost_elements_table = _collection_charge_cost_table
_base._clause = _collection_clause
_base.SimpleDocTemplate = _MandateAwareSimpleDocTemplate
_base._contract_pdf = _contract_pdf