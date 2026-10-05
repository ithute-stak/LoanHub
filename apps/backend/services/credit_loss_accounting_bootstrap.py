from __future__ import annotations

from sqlalchemy.orm import Session

from database.models.accounting import AccountingAccount
from services.accounting_service import ensure_chart, scope_key


PROVISION_ACCOUNTS = (
    ("1150", "Allowance for Credit Losses", "asset", "credit", "Contra-asset allowance against loans receivable."),
    ("5510", "Credit Loss Provision Expense", "expense", "debit", "Expense or release arising from an approved credit-loss provision run."),
)


def ensure_credit_loss_accounts(db: Session, company_id) -> None:
    ensure_chart(db, company_id=company_id)
    key, scope_type = scope_key(company_id)
    existing = {
        row.code
        for row in db.query(AccountingAccount).filter(
            AccountingAccount.scope_key == key,
            AccountingAccount.code.in_([code for code, *_ in PROVISION_ACCOUNTS]),
        ).all()
    }
    for code, name, account_type, normal_balance, description in PROVISION_ACCOUNTS:
        if code in existing:
            continue
        db.add(AccountingAccount(
            scope_key=key,
            scope_type=scope_type,
            company_id=company_id,
            code=code,
            name=name,
            account_type=account_type,
            normal_balance=normal_balance,
            description=description,
            is_system=True,
            is_active=True,
        ))
    db.flush()
