from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_studio_assets_loaded():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "/app/studio-panels.css" in html
    assert "/app/studio-panels.js" in html


def test_studio_workspaces_are_functional():
    js = (WEB / "studio-panels.js").read_text(encoding="utf-8")
    for token in (
        "Code Studio",
        "Video Studio",
        "Shopify Studio",
        "File Studio",
        "Automation Studio",
        "requestSubmit",
        "/integrations/n8n/health",
        "atlasFileCenter",
        "writeModeBtn",
        "claudeReviewBtn",
    ):
        assert token in js


def test_shopify_studio_keeps_publish_confirmation_boundary():
    js = (WEB / "studio-panels.js").read_text(encoding="utf-8")
    assert "Перед публикацией или опасным изменением запроси подтверждение" in js
