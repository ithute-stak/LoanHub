"""Nedbank Lesotho native-text PDF statement adapter.

Returns no lending decision. A validated balance chain establishes arithmetic
consistency, NOT the authenticity of an uploaded bank statement.
Never log extracted text: it contains personal and financial information.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from services.document_intelligence_foundation import BankTransaction, money, validate_statement_balances
from services.document_intelligence_reader import (
    DocumentReadError, MAX_INPUT_BYTES, MAX_PAGES, _run, PDF_RENDER_TIMEOUT_SECONDS,
)

DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
AMOUNT_PATTERN = r"[\d,]+\.\d{2}"
TRANSACTION = re.compile(
    rf"^\s*(?P<txdate>{DATE_PATTERN})\s+(?P<valuedate>{DATE_PATTERN})"
    rf"\s+(?P<reference>\S+(?:[ ]\S+)?)(?:\s{{2,}})"
    rf"(?P<description>.+?)\s{{2,}}(?P<amount>{AMOUNT_PATTERN})"
    rf"\s+(?P<balance>{AMOUNT_PATTERN})\s*$"
)
MONTH = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})\s+Statement\b", re.I
)


class NedbankStatementError(ValueError):
    pass


@dataclass(frozen=True)
class NedbankRow:
    transaction_date: date
    value_date: date
    reference: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


@dataclass(frozen=True)
class NedbankStatement:
    statement_year: int
    statement_month: int
    account_number: str
    customer_name: str
    customer_id: str
    branch_code: str
    currency: str
    opening_balance: Decimal
    closing_balance: Decimal
    rows: tuple[NedbankRow, ...]
    total_debits: Decimal
    total_credits: Decimal
    reconciled: bool
    review_required: bool = True


def _field(text: str, name: str) -> str:
    """Extract either column of the Nedbank two-column statement header."""
    pattern = (
        r"(?im)(?:^|[ \\t]{3,})" + re.escape(name)
        + r":[ \t]*(.*?)(?=[ \t]{3,}[A-Za-z][A-Za-z ]+:|$)"
    )
    match = re.search(pattern, text)
    if not match or not match.group(1).strip():
        raise NedbankStatementError("required statement header missing: " + name)
    return match.group(1).strip()


def parse_nedbank_layout(text: str) -> NedbankStatement:
    """Parse preserved-column text; fail closed on malformed or omitted dated rows.

    Use pdftotext -layout as the text source, not OCR text flattened into one line.
    Scanned statements must be reviewed until a table-aware OCR adapter is ready.
    """
    match = MONTH.search(text)
    if not match:
        raise NedbankStatementError("unrecognised Nedbank statement period")
    import calendar
    month = list(calendar.month_name).index(match.group(1).title())
    year = int(match.group(2))
    account = _field(text, "Account Number")
    name = _field(text, "Customer Name")
    customer_id = _field(text, "Customer Id")
    branch_code = _field(text, "Branch Code")
    currency = _field(text, "Currency")
    opening = money(_field(text, "Opening Balance"))
    closing = money(_field(text, "Closing Balance"))
    if not re.fullmatch(r"\d{7,20}", account) or currency != "LSL":
        raise NedbankStatementError("invalid account or unsupported currency")
    if not re.fullmatch(r"\d{2,6}", branch_code):
        raise NedbankStatementError("invalid branch code")
    rows: list[NedbankRow] = []
    current = opening
    for line in text.splitlines():
        if not re.match(rf"^\s*{DATE_PATTERN}\s+{DATE_PATTERN}\s+", line):
            continue
        matched = TRANSACTION.match(line)
        if not matched:
            raise NedbankStatementError("unparseable dated transaction row")
        data = matched.groupdict()
        try:
            tx_date = date.fromisoformat(data["txdate"])
            value_date = date.fromisoformat(data["valuedate"])
            amount = money(data["amount"])
            balance = money(data["balance"])
        except ValueError as exc:
            raise NedbankStatementError("malformed dated transaction") from exc
        if tx_date.year != year or tx_date.month != month:
            raise NedbankStatementError("transaction date does not match statement period")
        if amount <= 0 or balance == current:
            raise NedbankStatementError("invalid or zero-effect transaction")
        debit = amount if balance < current else Decimal("0.00")
        credit = amount if balance > current else Decimal("0.00")
        if current - debit + credit != balance:
            raise NedbankStatementError("transaction running balance mismatch")
        rows.append(NedbankRow(
            tx_date, value_date, data["reference"], data["description"].strip(),
            debit, credit, balance
        ))
        current = balance
    if not rows:
        raise NedbankStatementError("no statement transactions extracted")
    if not validate_statement_balances(opening, closing, [
        BankTransaction(x.debit, x.credit, x.balance) for x in rows
    ]):
        raise NedbankStatementError("statement balance reconciliation failed")
    return NedbankStatement(
        year, month, account, name, customer_id, branch_code, currency, opening, closing,
        tuple(rows), sum((x.debit for x in rows), Decimal("0.00")),
        sum((x.credit for x in rows), Decimal("0.00")), True,
    )


def parse_nedbank_native_pdf(contents: bytes) -> NedbankStatement:
    """Use bounded native-text extraction; scanned PDFs need a separate review flow."""
    if not contents.startswith(b"%PDF-") or len(contents) > MAX_INPUT_BYTES:
        raise NedbankStatementError("invalid or oversized PDF")
    try:
        reader = PdfReader(BytesIO(contents), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            raise NedbankStatementError("encrypted or excessive-page PDF")
    except NedbankStatementError:
        raise
    except Exception as exc:
        raise NedbankStatementError("cannot read PDF metadata") from exc
    with TemporaryDirectory(prefix="loanhub-nedbank-") as temp:
        path = Path(temp) / "statement.pdf"
        path.write_bytes(contents)
        try:
            layout = _run(
                ["pdftotext", "-layout", str(path), "-"],
                timeout=PDF_RENDER_TIMEOUT_SECONDS,
            ).decode("utf-8")
        except (DocumentReadError, UnicodeError) as exc:
            raise NedbankStatementError("native PDF text extraction failed") from exc
    return parse_nedbank_layout(layout)


def validate_nedbank_series(statements: list[NedbankStatement]) -> bool:
    """Same account and uninterrupted adjacent calendar months, with linked balances."""
    if not statements:
        return False
    ordered = sorted(statements, key=lambda s: (s.statement_year, s.statement_month))
    if len({(s.statement_year, s.statement_month) for s in ordered}) != len(ordered):
        return False
    for left, right in zip(ordered, ordered[1:]):
        if (right.statement_year * 12 + right.statement_month) != (left.statement_year * 12 + left.statement_month + 1):
            return False
        if (left.account_number != right.account_number or
                left.customer_name != right.customer_name or
                left.closing_balance != right.opening_balance):
            return False
    return True
