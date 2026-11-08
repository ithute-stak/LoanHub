"""The retired quick-affordability integration cannot block marketplace offers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quick_offers_use_term_calculation_without_affordability_checks():
    router = (ROOT / "routers/loan_offers.py").read_text(encoding="utf-8")
    assert "async def _calculate_offer_terms(" in router
    assert "async def create_offer(" in router
    assert "async def update_offer(" in router
    assert router.count("await _calculate_offer_terms(") == 2
    assert "quick_loan_affordability(" not in router
    assert '@router.post("/quick-affordability-preview")' not in router
    assert "calculate_offer_totals(" in router
