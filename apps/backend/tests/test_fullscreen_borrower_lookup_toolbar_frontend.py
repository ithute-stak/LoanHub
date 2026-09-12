from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_fullscreen_toolbar_keeps_expanded_national_id_lookup_visible() -> None:
    portal = read("components/portal/portal-shell.tsx")

    assert 'className="fixed inset-x-2 top-2' in portal
    assert '<GlobalBorrowerLookup forceExpanded className="max-w-xl" />' in portal
    assert '<GlobalBorrowerLookup compact />' not in portal
    assert 'pt-[4.5rem]' in portal
    assert portal.index('<GlobalBorrowerLookup forceExpanded') < portal.index('<WorkspaceModeToggle />', portal.index('<GlobalBorrowerLookup forceExpanded'))


def test_lookup_supports_a_forced_expanded_layout_without_icon_fallback() -> None:
    lookup = read("components/clients/global-borrower-lookup.tsx")

    assert "forceExpanded?: boolean" in lookup
    assert 'forceExpanded ? "flex flex-1" : "hidden xl:flex"' in lookup
    assert 'data-borrower-lookup-mode={forceExpanded ? "expanded" : "responsive"}' in lookup
    assert 'forceExpanded ? "min-w-0 flex-1"' in lookup
    assert '!forceExpanded ? <span className="xl:hidden">{compactButton}</span> : null' in lookup
