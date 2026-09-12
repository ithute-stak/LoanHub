from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class LegacyLoanCapture(Base):
    """An immutable transcription of one historic cash-out-book entry.

    This table is intentionally separate from live payment transactions. Posting a
    capture creates a normal LoanHub loan and schedule, but it never pretends that
    historic cash was received or disbursed through LoanHub.
    """

    __tablename__ = "legacy_loan_captures"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    captured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    company_borrower_account_id = Column(UUID(as_uuid=True), ForeignKey("company_borrower_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)

    folio_number = Column(String(80), nullable=False, index=True)
    cashout_book_number = Column(String(80), nullable=True)
    page_number = Column(String(80), nullable=True)
    entry_number = Column(String(80), nullable=True)
    book_date = Column(Date, nullable=True)

    surname = Column(String(100), nullable=True)
    names = Column(String(220), nullable=True)
    passport_number = Column(String(100), nullable=True)
    national_id = Column(String(100), nullable=True)
    # The legacy migration called this column id_expiry_date. It is deliberately
    # exposed only as a passport expiry: a Lesotho national ID has no expiry date.
    passport_expiry_date = Column("id_expiry_date", Date, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    residential_address = Column(Text, nullable=True)
    postal_address = Column(Text, nullable=True)
    employer = Column(String(200), nullable=True)
    occupation = Column(String(150), nullable=True)
    net_pay = Column(Numeric(15, 2), nullable=True)
    employee_number = Column(String(100), nullable=True)
    cell_phone = Column(String(30), nullable=True)
    home_phone = Column(String(30), nullable=True)
    work_phone = Column(String(30), nullable=True)
    next_of_kin_contact = Column(String(30), nullable=True)
    next_of_kin_work_phone = Column(String(30), nullable=True)
    next_of_kin_name = Column(String(200), nullable=True)
    next_of_kin_relationship = Column(String(100), nullable=True)

    borrowed_amount = Column(Numeric(15, 2), nullable=True)
    total_repayable = Column(Numeric(15, 2), nullable=True)
    amount_paid = Column(Numeric(15, 2), nullable=True)
    installment_count = Column(Integer, nullable=True)
    installment_amount = Column(Numeric(15, 2), nullable=True)
    repayment_type = Column(String(20), nullable=True)
    calculation_method = Column(String(80), nullable=True)

    banking_info = Column(JSONB, nullable=False, default=dict)
    bank_account_number_encrypted = Column(Text, nullable=True)
    bank_account_number_last4 = Column(String(4), nullable=True)

    # Captured text/calculator values are retained verbatim for audit. Conversion
    # values record the safe normalisation decision without rewriting the evidence.
    paper_snapshot = Column(JSONB, nullable=False, default=dict)
    conversion_data = Column(JSONB, nullable=False, default=dict)

    status = Column(String(30), nullable=False, default="draft", index=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    converted_at = Column(DateTime(timezone=True), nullable=True)
