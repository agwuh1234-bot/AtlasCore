from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "web" / "runtime-refresh.js"


def test_login_guard_forces_modal_above_workspace():
    text = RUNTIME.read_text(encoding="utf-8")
    assert "installLoginGuard" in text
    assert "atlas-login-open" in text
    assert "z-index:2147483646" in text
    assert "#loginCard input" in text
    assert "pointer-events:auto!important" in text


def test_login_guard_restores_touch_focus_on_safari():
    text = RUNTIME.read_text(encoding="utf-8")
    assert "touchend" in text
    assert "pointerup" in text
    assert "input.focus" in text
    assert "atlas-right-open" in text
    assert "atlas-dialog-open" in text
