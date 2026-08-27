from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_functional_ui_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    assert '/app/ui-actions.css' in index
    assert '/app/ui-actions.js' in index


def test_reference_dashboard_has_real_action_targets():
    script = (WEB / "ui-actions.js").read_text(encoding="utf-8")
    for token in [
        "openTemplates",
        "openIntegrations",
        "openToolManager",
        "openProjectSwitcher",
        "openQuickMenu",
        "#fileInput",
        "#newChatBtn",
        "#settingsBtn",
        "#claudeReviewBtn",
        "data-tab",
    ]:
        assert token in script


def test_dashboard_core_controls_are_not_dead_placeholders():
    script = (WEB / "dashboard.js").read_text(encoding="utf-8")
    for label in [
        "Code Studio",
        "Video Studio",
        "Shopify Studio",
        "File Studio",
        "Сводка проекта",
        "Улучшить текст",
        "Создать план",
        "Найти решения",
    ]:
        assert label in script
    assert ".onclick" in script


def test_ui_actions_avoid_javascript_urls_and_inline_navigation_hacks():
    script = (WEB / "ui-actions.js").read_text(encoding="utf-8").lower()
    assert "javascript:" not in script
    assert "window.open(" not in script
