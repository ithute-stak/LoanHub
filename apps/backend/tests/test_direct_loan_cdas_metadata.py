from __future__ import annotations

import subprocess
import sys


def test_direct_loan_import_registers_cdas_foreign_key_targets() -> None:
    """The company-client loan path imports professional_lending directly.

    Keep this test in an isolated Python process so it cannot accidentally pass
    because another pytest module imported the CDAS booking models first.
    """

    code = r'''
from database.base import Base
from database.models.professional_lending import DirectLoanApplication

expected_targets = {
    "cdas_source_opportunity_id": "cdas_booking_opportunities",
    "cdas_source_analysis_id": "cdas_analysis_records",
}

for column_name, table_name in expected_targets.items():
    assert table_name in Base.metadata.tables, (
        f"{table_name} must be registered when professional_lending is imported directly"
    )
    column = DirectLoanApplication.__table__.c[column_name]
    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.column.table is Base.metadata.tables[table_name]
'''

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
