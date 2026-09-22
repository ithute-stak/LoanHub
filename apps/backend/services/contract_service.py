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
    """Freeze the collection-charge policy into a new contract.

    Existing contracts are deliberately left untouched. This prevents a later company
    setting from being injected into a legacy agreement that the borrower never signed.
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
    terms["template_version"] = "3.1-collection-charge-controls"
    terms["collection_charge"] = _company_collection_charge_policy(db, loan.company_id)
    return terms


def _collection_charge_cost_table(
    terms: dict[str, Any],
    styles: dict[str, Any],
) -> Any:
    policy = normalize_collection_charge_policy(
        {"collection_charge": terms.get("collection_charge") or {}}
    )
    if not policy["enabled"]:
        return _original_cost_elements_table(terms, styles)

    processing_fee = _base._as_decimal(terms.get("processing_fee"))
    total_fees = _base._as_decimal(terms.get("total_fees"))
    other_fees = max(total_fees - processing_fee, _base.Decimal("0"))
    rows = [
        ["2.1 Amount of interest charged", _base._money(terms.get("total_interest"))],
        ["2.2 Initiation / processing fee", _base._money(processing_fee)],
        ["2.3 Other service and schedule fees", _base._money(other_fees)],
        ["2.4 Taxes included in disclosed charges", _base._money(terms.get("tax_amount"))],
        [
            "2.5 Conditional collection / recovery charge",
            collection_charge_disclosure(policy),
        ],
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


def _collection_clause(
    number: str,
    heading: str,
    text: str,
    styles: dict[str, Any],
) -> list[Any]:
    elements = _original_clause(number, heading, text, styles)
    if number != "12":
        return elements

    terms = _active_contract_terms.get()
    policy = normalize_collection_charge_policy(
        {"collection_charge": terms.get("collection_charge") or {}}
    )
    if not policy["enabled"]:
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
# extension points needed for the new signed collection-charge controls.
_base.build_terms = build_terms
_base._cost_elements_table = _collection_charge_cost_table
_base._clause = _collection_clause
_base._contract_pdf = _contract_pdf
