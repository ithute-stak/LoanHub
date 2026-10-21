"""Overdue loan portfolio indicators must be accessible, interactive shortcuts."""
from pathlib import Path

UI = (Path(__file__).resolve().parents[2] / "frontend/components/loans/loan-portfolio-workspace.tsx").read_text()


def test_overdue_badges_filter_portfolio_in_both_views():
    assert UI.count('onClick={() => applyQuickFilter("overdue")}') >= 3
    assert UI.count('aria-label="Show overdue loans"') == 2
    assert 'if (kind === "overdue") setFilters((current) => ({...current, overdue: "yes"}))' in UI
    assert 'if (filters.overdue === "yes" && !loan.is_overdue) return false;' in UI
    assert 'title="Filter portfolio to overdue loans"' in UI
