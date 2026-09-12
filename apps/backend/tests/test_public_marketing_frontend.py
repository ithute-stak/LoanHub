from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_APP = REPOSITORY_ROOT / "apps" / "frontend" / "app"


def test_root_is_public_website_not_timed_redirect():
    source = (FRONTEND_APP / "page.tsx").read_text()
    assert "setTimeout" not in source
    assert "router.replace" not in source
    assert "LivePlatformStats" in source
    assert 'href="/manual"' in source
    assert 'href="/documentation"' in source
    assert 'href="/borrower-registration"' in source
    assert 'href="/register-company-admin"' in source


def test_public_manual_and_documentation_exist():
    manual = (FRONTEND_APP / "manual" / "page.tsx").read_text()
    documentation = (FRONTEND_APP / "documentation" / "page.tsx").read_text()

    for expected in (
        "Borrower guide",
        "Institution setup",
        "Lending lifecycle",
        "Accounting, reconciliation and reporting",
        "Security, privacy and evidence",
        "Troubleshooting and safe support",
    ):
        assert expected in manual

    assert "Operational checklists" in documentation
    assert "Production boundaries" in documentation
    assert "/privacy/loanhub-mobile" in documentation
