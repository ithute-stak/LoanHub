from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MOBILE_CSS = ROOT / "frontend" / "app" / "mobile-app.css"
ROOT_LAYOUT = ROOT / "frontend" / "app" / "layout.tsx"
PULL_REFRESH = ROOT / "frontend" / "components" / "system" / "mobile-pull-to-refresh.tsx"


def test_mobile_root_guarantees_vertical_scrolling_without_unlocking_nested_panes():
    source = MOBILE_CSS.read_text(encoding="utf-8")

    assert "overflow-y: auto;" in source
    assert "overflow-x: hidden;" in source
    assert "-webkit-overflow-scrolling: touch;" in source
    assert "overscroll-behavior-y: none;" in source
    assert "main > .h-screen" in source
    assert "main > .h-dvh" in source
    assert "main > .h-full" in source
    assert "main > .overflow-hidden" in source
    assert "overflow-y: visible !important;" in source
    assert '[data-slot="dialog-content"]' in source


def test_pull_to_refresh_is_global_mobile_only_and_gesture_safe():
    layout = ROOT_LAYOUT.read_text(encoding="utf-8")
    source = PULL_REFRESH.read_text(encoding="utf-8")

    assert 'import MobilePullToRefresh from "@/components/system/mobile-pull-to-refresh";' in layout
    assert "<MobilePullToRefresh />" in layout

    assert 'window.matchMedia("(max-width: 1023.98px) and (pointer: coarse)")' in source
    assert "navigator.maxTouchPoints > 0" in source
    assert 'document.addEventListener("touchstart"' in source
    assert 'document.addEventListener("touchmove"' in source
    assert 'document.addEventListener("touchend"' in source
    assert "{ passive: false }" in source
    assert "scrollTopOf(scrollContainer.current) > 1" in source
    assert "Math.abs(deltaX) > Math.abs(deltaY)" in source
    assert "event.preventDefault()" in source
    assert "[contenteditable='true']" in source
    assert "[role='dialog']" in source
    assert "[data-disable-pull-refresh]" in source
    assert 'new CustomEvent("loanhub:pull-refresh"' in source
    assert "window.location.reload()" in source
    assert "Pull to refresh" in source
    assert "Release to refresh" in source
    assert "Refreshing data…" in source
