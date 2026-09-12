from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "frontend"


def test_reusable_sticky_filter_bar_has_css_fallback_and_floating_state():
    source = (FRONTEND / "components/ui/sticky-filter-bar.tsx").read_text(
        encoding="utf-8"
    )

    assert 'floating ? "fixed" : "sticky"' in source
    assert "top-[calc(var(--loanhub-sticky-filter-top)_+_env" in source
    assert "IntersectionObserver" in source
    assert 'data-floating={floating ? "true" : "false"}' in source
    assert "useWorkspaceFullscreen" in source
    assert 'role={landmarkRole}' in source
    assert 'landmarkRole = "search"' in source


def test_company_client_filters_use_the_sticky_toolbar():
    source = (
        FRONTEND / "app/(dashboard)/company/clients/page.tsx"
    ).read_text(encoding="utf-8")

    assert 'import { StickyFilterBar }' in source
    assert '<StickyFilterBar' in source
    assert 'ariaLabel="Company client search and filters"' in source
    assert 'className="overflow-visible rounded-3xl' in source
    assert 'CardContent className="overflow-hidden rounded-b-3xl p-0"' in source
