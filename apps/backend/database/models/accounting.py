from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class AccountingAccount(Base):
    __tablename__ = "accounting_accounts"
    __table_args__ = (
        UniqueConstraint("scope_key", "code", name="uq_accounting_scope_code"),
    )

    scope_key = Column(String(80), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, default="company", index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    code = Column(String(30), nullable=False)
    name = Column(String(180), nullable=False)
    account_type = Column(String(30), nullable=False, index=True)
    normal_balance = Column(String(10), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    parent = relationship("AccountingAccount", remote_side="AccountingAccount.id")


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("scope_key", "entry_number", name="uq_journal_scope_number"),
        UniqueConstraint(
            "scope_key",
            "reference_type",
            "reference_id",
            name="uq_journal_scope_reference",
        ),
    )

    scope_key = Column(String(80), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, default="company", index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    posted_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    entry_number = Column(String(60), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    description = Column(Text, nullable=False)
    reference_type = Column(String(80), nullable=True, index=True)
    reference_id = Column(String(120), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    total_debit = Column(Numeric(18, 2), nullable=False, default=0)
    total_credit = Column(Numeric(18, 2), nullable=False, default=0)
    posted_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    lines = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.created_at",
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    description = Column(String(500), nullable=True)
    debit = Column(Numeric(18, 2), nullable=False, default=0)
    credit = Column(Numeric(18, 2), nullable=False, default=0)

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("AccountingAccount")
