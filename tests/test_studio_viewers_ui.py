from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_studio_viewer_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    assert '/app/studio-viewers.css' in index
    assert '/app/studio-viewers.js' in index
    assert index.index('/app/studio-viewers.js') < index.index('/app/studio-results.js')


def test_studio_viewers_cover_all_core_modes():
    js = (WEB / "studio-viewers.js").read_text(encoding="utf-8")
    for mode in ("code", "video", "shopify", "files", "automation"):
        assert f"r.mode==='{mode}'" in js or f"mode==='${mode}'" in js or mode in js
    assert 'studio-diff-line' in js
    assert 'studio-storyboard' in js
    assert 'shopify-preview' in js
    assert 'file-preview-chip' in js
    assert 'automation-flow' in js


def test_studio_results_open_rich_viewer():
    js = (WEB / "studio-results.js").read_text(encoding="utf-8")
    assert 'AtlasStudioViewer' in js
    assert "button('Открыть'" in js
    assert 'atlas-studio-results-changed' in js
