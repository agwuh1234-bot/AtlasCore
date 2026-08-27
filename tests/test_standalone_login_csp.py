from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_standalone_login_uses_external_assets_only():
    html = (WEB / "login.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/app/login.css' in html
    assert '<script src="/app/login.js' in html
    assert "<style>" not in html
    assert "<script>" not in html


def test_standalone_login_preserves_safari_touch_focus_and_stacking():
    script = (WEB / "login.js").read_text(encoding="utf-8")
    styles = (WEB / "login.css").read_text(encoding="utf-8")
    assert "pointerdown" in script
    assert "touchend" in script
    assert "focusInput" in script
    assert "pointer-events:auto!important" in styles
    assert "z-index:2147483647" in styles


def test_standalone_login_does_not_load_main_pwa_runtime():
    html = (WEB / "login.html").read_text(encoding="utf-8")
    for forbidden in ("app.js", "runtime-refresh.js", "sw.js", "manifest.json"):
        assert forbidden not in html
