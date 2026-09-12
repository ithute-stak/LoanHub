from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BORROWER_LAYOUT = ROOT / "apps/frontend/app/(dashboard)/borrower/layout.tsx"
MOBILE_APP_CSS = ROOT / "apps/frontend/app/mobile-app.css"
MOBILE_NAV = ROOT / "apps/frontend/components/navigation/mobile-app-navigation.tsx"


def test_borrower_layout_uses_document_flow_instead_of_a_nested_viewport_scroller() -> None:
    source = BORROWER_LAYOUT.read_text(encoding="utf-8")

    assert "data-loanhub-borrower-scroll" in source
    assert "data-loanhub-scroll-root" in source
    assert 'min-h-[100dvh]' in source
    assert "overflow-x-hidden" in source
    assert "overflow-y-visible" in source
    assert "overscroll-y-auto" in source
    assert "touch-pan-y" in source

    # A full-height overflow-y-auto wrapper creates a second scroll owner and
    # can trap touch gestures on Safari/Chrome mobile. Check the Tailwind class
    # as an exact token so `min-h-[100dvh]` is not mistaken for `h-[100dvh]`.
    class_tokens = source.replace('"', " ").split()
    assert 'h-[100dvh]' not in class_tokens
    assert "overflow-y-auto" not in class_tokens
    assert "overscroll-y-contain" not in class_tokens
    assert '<PortalShell mode="borrower">{children}</PortalShell>' in source


def test_global_mobile_shell_makes_the_document_the_vertical_scroll_owner() -> None:
    source = MOBILE_APP_CSS.read_text(encoding="utf-8")

    assert "One vertical scroll owner on phones: the document" in source
    assert "body > main#main-content" in source
    assert "[data-loanhub-scroll-root]" in source
    assert "overflow-y: visible !important;" in source
    assert "overscroll-behavior-y: auto;" in source
    assert "overscroll-behavior-y: none;" in source
    assert "touch-action: pan-y pinch-zoom;" in source
    assert "padding-bottom: calc(5.25rem + env(safe-area-inset-bottom, 0px)) !important;" in source


def test_mobile_tables_keep_horizontal_scroll_without_stealing_vertical_touch() -> None:
    source = MOBILE_APP_CSS.read_text(encoding="utf-8")

    assert '[data-slot="table-container"]' in source
    assert ".loanhub-responsive-scroll" in source
    assert "overflow-x: auto;" in source
    assert "overflow-y: visible;" in source
    assert "touch-action: pan-x pan-y;" in source


def test_mobile_dialogs_and_navigation_sheets_remain_bounded_scroll_regions() -> None:
    css = MOBILE_APP_CSS.read_text(encoding="utf-8")
    navigation = MOBILE_NAV.read_text(encoding="utf-8")

    assert '[data-slot="dialog-content"]' in css
    assert "max-height: calc(100dvh - 1rem);" in css
    assert "overflow-y: auto;" in css

    assert 'max-h-[84dvh]' in navigation
    assert "min-h-0 flex-1 overflow-y-auto overscroll-contain" in navigation
    assert 'document.body.style.overflow = "hidden"' in navigation
