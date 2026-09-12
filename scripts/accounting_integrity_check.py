#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from decimal import Decimal

from sqlalchemy import create_engine, text


CHECKS = {
    'unbalanced journal headers': """
        SELECT count(*) FROM journal_entries
        WHERE COALESCE(total_debit, 0) <> COALESCE(total_credit, 0)
    """,
    'unbalanced journal lines': """
        SELECT count(*)
        FROM (
          SELECT je.id
          FROM journal_entries je
          JOIN journal_lines jl ON jl.journal_entry_id = je.id
          GROUP BY je.id
          HAVING COALESCE(SUM(jl.debit), 0) <> COALESCE(SUM(jl.credit), 0)
        ) broken
    """,
    'invalid double-sided journal lines': """
        SELECT count(*) FROM journal_lines
        WHERE (COALESCE(debit, 0) > 0 AND COALESCE(credit, 0) > 0)
           OR (COALESCE(debit, 0) = 0 AND COALESCE(credit, 0) = 0)
    """,
}


def main() -> int:
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('DATABASE_URL must be set', file=sys.stderr)
        return 2
    engine = create_engine(database_url, pool_pre_ping=True)
    failures = []
    with engine.connect() as connection:
        for name, statement in CHECKS.items():
            count = int(connection.execute(text(statement)).scalar_one())
            print(f'{name}: {count}')
            if count:
                failures.append(name)
        trial = connection.execute(
            text('SELECT COALESCE(SUM(total_debit), 0), COALESCE(SUM(total_credit), 0) FROM journal_entries')
        ).one()
        if Decimal(trial[0]) != Decimal(trial[1]):
            failures.append('general-ledger control totals')
    if failures:
        print('Accounting integrity check FAILED: ' + ', '.join(failures), file=sys.stderr)
        return 1
    print('Accounting integrity check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
