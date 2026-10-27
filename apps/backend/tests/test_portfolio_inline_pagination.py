"""The ordinary portfolio view shares pagination and filters with the workspace."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/components/loans/loan-portfolio-workspace.tsx"
source = PAGE.read_text(encoding="utf-8")


def test_compact_table_uses_page_rows_and_page_controls():
    assert 'rows={pageRows}' in source
    assert 'Page {safePage} of {totalPages}' in source
    assert 'onClick={() => setPage(totalPages)}' in source
    assert 'onClick={() => setPage(1)}' in source


def test_compact_filters_are_operational():
    assert 'onClick={() => applyQuickFilter("overdue")}' in source
    assert 'onClick={() => applyQuickFilter("due7")}' in source
    assert 'onClick={() => setExpanded(true)}' in source
    assert 'disabled={!activeFilterCount} onClick={resetFilters}' in source
    assert 'onValueChange={(value) => setPageSize(Number(value))}' in source
