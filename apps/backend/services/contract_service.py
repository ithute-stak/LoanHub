from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy.orm import Session

import services.contract_service_base as _base
from database.models.origination import LoanContract, OriginationIntegrationConfiguration
from services.contract_service_base import *  # noqa: F401,F403
from services.lelefa_managed_collections import (
    PROVIDER,
    collection_charge_disclosure,
    normalize_collection_charge_policy,
)


EXPLICIT_COLLECTION_TEMPLATE_VERSION = "3.2-explicit-collection-cost-basis"

_original_build_terms = _base.build_terms
_original_contract_pdf = _base._contract_pdf
_original_clause = _base._clause
_original_cost_elements_table = _base._cost_elements_table
_active_contract_terms: ContextVar[dict[str, Any]] = ContextVar(
    "active_contract_terms",
    default={},
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
    """Freeze the collection-charge policy and legal wording into a new contract.

    Existing contracts are deliberately left untouched. This prevents a later company
    setting or wording revision from being injected into an agreement the borrower did
    not sign.
    """
    terms = _original_build_terms(db, loan)
    existing_contract = (
        db.query(LoanContract)
        .filter(LoanContract.loan_id == loan.id)
        .first()
    )
    if existing_contract is not None:
        return terms

    terms = dict(terms)
    terms["template_version"] = EXPLICIT_COLLECTION_TEMPLATE_VERSION
    terms["collection_charge"] = _company_collection_charge_policy(db, loan.company_id)
    return terms


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
    """Render the signed contractual basis for collection and recovery costs.

    The wording deliberately separates actual lawful external recovery costs from a
    percentage/fixed collection commission. A configured commission is enforceable by
    LoanHub only when it was frozen into and disclosed by the signed agreement.
    """
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

    if template_version == EXPLICIT_COLLECTION_TEMPLATE_VERSION:
        if number == "11":
            return _explicit_collection_clause(styles, policy)
        # The new template keeps all collection obligations under clause 11, so do
        # not duplicate the legacy 12.1 collection paragraph after enforcement.
        return _original_clause(number, heading, text, styles)

    # Backward compatibility is intentional. Signed 3.0/3.1 contracts must render
    # exactly the terms that existed when they were accepted; do not inject the new
    # legal wording into historical agreements during PDF regeneration.
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


def _contract_pdf(db: Session, contract: LoanContract) -> bytes:
    token = _active_contract_terms.set(
        contract.terms_snapshot if isinstance(contract.terms_snapshot, dict) else {}
    )
    try:
        return _original_contract_pdf(db, contract)
    finally:
        _active_contract_terms.reset(token)


# Keep the original rendering implementation intact while replacing only the narrow
# extension points needed for the signed collection-charge controls.
_base.build_terms = build_terms
_base._cost_elements_table = _collection_charge_cost_table
_base._clause = _collection_clause
_base._contract_pdf = _contract_pdf
