from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle


_BORDER = colors.HexColor("#8A94A6")
_MUTED = colors.HexColor("#5B6472")
_HEADING = colors.HexColor("#172033")
_PALE = colors.HexColor("#F6F8FB")
_HIGHLIGHT = colors.HexColor("#E9F7F5")


def _text(value: Any, fallback: str = "________________") -> str:
    rendered = str(value or "").strip()
    return escape(rendered) if rendered else fallback


def _money(value: Any) -> str:
    try:
        return f"M {float(value):,.2f}"
    except (TypeError, ValueError):
        return "________________"


def _date(value: Any, fallback: str = "________________") -> str:
    rendered = str(value or "").strip()
    if not rendered:
        return fallback
    return escape(rendered[:10])


def _payment_day(terms: Mapping[str, Any]) -> str:
    preferred = str(terms.get("preferred_payment_day") or "").strip()
    if preferred:
        return escape(preferred)
    first_due = str(terms.get("first_payment_due") or "").strip()
    if len(first_due) >= 10:
        try:
            return str(int(first_due[8:10]))
        except ValueError:
            pass
    return "____"


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "MandateTitle",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            textColor=_HEADING,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "MandateSection",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=8.4,
            leading=10.5,
            textColor=_HEADING,
            spaceBefore=4,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "MandateBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.35,
            leading=9.2,
            textColor=colors.black,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "MandateSmall",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=6.8,
            leading=8.2,
            textColor=_MUTED,
        ),
        "field_label": ParagraphStyle(
            "MandateFieldLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=8.5,
            textColor=_HEADING,
        ),
        "field_value": ParagraphStyle(
            "MandateFieldValue",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=8.5,
            textColor=colors.black,
        ),
        "execution": ParagraphStyle(
            "MandateExecution",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9.4,
            textColor=_HEADING,
        ),
    }


def _field_table(rows: list[tuple[str, str]], styles: Mapping[str, ParagraphStyle]) -> Table:
    data = [
        [Paragraph(label, styles["field_label"]), Paragraph(value, styles["field_value"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[51 * mm, 123 * mm], repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.45, _BORDER),
                ("BACKGROUND", (0, 0), (0, -1), _PALE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_debit_order_mandate(
    terms: Mapping[str, Any],
    *,
    agreement_reference: str,
    account_number: str | None,
) -> list[Any]:
    """Build the optional Authority to Debit Account as an incorporated contract annexure.

    The mandate retains the supplied authority, mandate, cancellation and assignment terms,
    but it no longer has a second borrower signature block. When this annexure is present,
    the final borrower signature on the credit agreement accepts and authorises it as part
    of the same contract.
    """
    styles = _styles()
    borrower = terms.get("borrower") if isinstance(terms.get("borrower"), Mapping) else {}
    company = terms.get("company") if isinstance(terms.get("company"), Mapping) else {}
    bank = terms.get("bank_account") if isinstance(terms.get("bank_account"), Mapping) else {}

    borrower_name = _text(bank.get("account_holder") or borrower.get("name"))
    borrower_address = _text(borrower.get("physical_address"))
    beneficiary_name = _text(company.get("name"))
    beneficiary_address = _text(company.get("address"))
    payment_day = _payment_day(terms)
    commencement_date = _date(terms.get("first_payment_due"), "____________")

    fields = [
        ("Given by (Name of account holder)", borrower_name),
        ("Address", borrower_address),
        ("Bank", _text(bank.get("bank_name"))),
        ("Branch code", _text(bank.get("branch_code"))),
        ("Account number", _text(account_number)),
        ("Account type", _text(bank.get("account_type"))),
        ("Amount", _money(terms.get("installment_amount"))),
        ("Date", _date(terms.get("agreement_date"))),
        ("To: (name of beneficiary)", beneficiary_name),
        ("Beneficiary's address", beneficiary_address),
        ("Abbreviated name as it will appear on your bank statement", "________________"),
    ]

    authority_left = [
        Paragraph(
            "This signed Authority and Mandate refers to our contract dated "
            f"<b>{_date(terms.get('agreement_date'))}</b> (\"the Agreement\").",
            styles["body"],
        ),
        Paragraph(
            "I/We hereby authorise you to issue and deliver payment instructions to your Banker for "
            "collection against my/our abovementioned account at my/our above-mentioned Bank (or any "
            "other Bank or branch to which I/we may transfer my/our account) on condition that the sum "
            "of such payment instructions will never exceed my/our obligations as agreed to in the "
            "Agreement, and commencing on "
            f"<b>{commencement_date}</b> and continuing until this Authority and Mandate is terminated "
            "by me/us by giving you notice in writing of not less 20 ordinary working days, and sent by "
            "prepaid registered post or delivered to your address indicated above.",
            styles["body"],
        ),
        Paragraph(
            "The individual payment instructions so authorised to be issued must be issued and delivered as follows:",
            styles["body"],
        ),
        Paragraph(
            "i. on the <b>" + payment_day + "</b> day (\"payment day\") of the month commencing on "
            f"<b>{commencement_date}</b>. In the event that the payment day falls on a Sunday or recognized "
            "public holiday, the payment day will automatically be the very next ordinary business day. "
            "Furthermore, if there are insufficient funds in the (my) nominated account to meet the "
            "obligation, you are entitled to track my account and re-present the instruction for payment "
            "as soon as sufficient funds are available in my account;",
            styles["body"],
        ),
        Paragraph(
            "ii. monthly, bi-monthly, three monthly, six-monthly, annually, weekly, bi-weekly or once-off "
            "(delete which is not applicable), on or after the dates when the obligation in terms of the "
            "Agreement is due and the amount of each individual payment instruction may not be more or less "
            "than the obligation due.",
            styles["body"],
        ),
        Paragraph(
            "Payment Instructions due in December and/or April may be debited against my account on "
            "________________.",
            styles["body"],
        ),
    ]

    authority_right = [
        Paragraph(
            "I/We understand that the withdrawals hereby authorised will be processed through a computerized "
            "system provided by the Banks. I also understand that details of each withdrawal will be printed "
            "on my Bank statement. Such must contain a number, which number must be included in the said "
            "payment instruction and if provided to me should enable me to identify the Agreement. This number "
            "must be added to this form in section D before the issuing of any payment instruction.",
            styles["body"],
        ),
        Paragraph("A. MANDATE", styles["section"]),
        Paragraph(
            "I/We acknowledge that all payment instructions issued by you shall be treated by my/our above "
            "mentioned Bank as if the instructions had been issued by me/us personally.",
            styles["body"],
        ),
        Paragraph("B. CANCELLATION", styles["section"]),
        Paragraph(
            "I/We agree that although this Authority and Mandate may be cancelled by me/us, such cancellation "
            "will not cancel the Agreement. I/We shall not be entitled to any refund of amounts which you have "
            "withdrawn while this Authority was in force, if such amounts were legally owing to you.",
            styles["body"],
        ),
        Paragraph("C. ASSIGNMENT", styles["section"]),
        Paragraph(
            "I/We acknowledge that this authority may be ceded or assigned to a third party if the Agreement "
            "is also ceded or assigned to that third party, but in the absence of such assignment of the "
            "Agreement, this Authority and Mandate cannot be assigned to any third party.",
            styles["body"],
        ),
    ]

    legal_table = Table(
        [[authority_left, authority_right]],
        colWidths=[86 * mm, 86 * mm],
        hAlign="CENTER",
    )
    legal_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEAFTER", (0, 0), (0, 0), 0.35, _BORDER),
            ]
        )
    )

    execution = KeepTogether(
        [
            Spacer(1, 3 * mm),
            Paragraph("D. AGREEMENT REFERENCE NUMBER", styles["section"]),
            Paragraph(
                f"This agreement reference number is: <b>{_text(agreement_reference)}</b>",
                styles["body"],
            ),
            Table(
                [[Paragraph(
                    "SINGLE SIGNATURE EXECUTION - The borrower does not sign this mandate page separately. "
                    "The borrower signature in Annexure C - Acceptance and Signatures applies to this mandate "
                    "and to the rest of the credit agreement as one contract.",
                    styles["execution"],
                )]],
                colWidths=[174 * mm],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), _HIGHLIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]),
            ),
        ]
    )

    return [
        PageBreak(),
        Paragraph("ANNEXURE B - AUTHORITY TO DEBIT ACCOUNT", styles["title"]),
        Paragraph(
            "This Authority to Debit Account is incorporated into and forms part of this credit agreement. "
            "It is accepted and authorised by the borrower's single signature in Annexure C - Acceptance and "
            "Signatures. No second borrower signature is required on this mandate page in LoanHub.",
            styles["small"],
        ),
        Spacer(1, 2 * mm),
        _field_table(fields, styles),
        Spacer(1, 4 * mm),
        legal_table,
        execution,
    ]