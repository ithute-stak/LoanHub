from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND = REPOSITORY_ROOT / "apps" / "frontend"


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_shared_form_primitives_use_comfortable_touch_targets():
    input_source = _read("components/ui/input.tsx")
    textarea_source = _read("components/ui/textarea.tsx")
    select_source = _read("components/ui/select.tsx")
    button_source = _read("components/ui/button.tsx")
    label_source = _read("components/ui/label.tsx")

    assert '"h-11 w-full min-w-0 rounded-xl' in input_source
    assert "focus-visible:ring-4" in input_source
    assert "min-h-28" in textarea_source
    assert "resize-y" in textarea_source
    assert "data-[size=default]:h-11" in select_source
    assert "w-full min-w-0" in select_source
    assert '"h-10 gap-2 px-4' in button_source
    assert '"h-12 gap-2 px-5 text-base' in button_source
    assert "font-semibold text-foreground" in label_source


def test_global_form_polish_covers_native_controls_and_mobile_zoom():
    css = _read("app/form-polish.css")
    layout = _read("app/layout.tsx")

    assert 'import "./form-polish.css";' in layout
    assert 'form input[type="text"]' in css
    assert 'form input[type="tel"]' in css
    assert "form select" in css
    assert "form textarea" in css
    assert "min-height: 2.75rem;" in css
    assert "font-size: 16px;" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css


def test_login_form_is_compact_without_changing_login_contract():
    css = _read("app/form-polish.css")
    login = _read("app/(auth)/login/page.tsx")

    for field_id in ("login-phone", "login-password", "login-second-factor"):
        assert field_id in login
        assert f"#{field_id}" in css

    assert "min-height: 3.25rem;" in css
    assert "height: 3rem;" in css
    assert "loginUser" in login
    assert "getDashboardRoute" in login
