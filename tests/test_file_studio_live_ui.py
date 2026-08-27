from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_live_file_studio_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    assert '/app/file-studio-live.css' in index
    assert '/app/file-studio-live.js' in index


def test_live_file_studio_uses_real_file_api_and_selection():
    js = (WEB / "file-studio-live.js").read_text(encoding="utf-8")
    assert '/app-files?project_id=' in js
    assert '/app-files/' in js
    assert "method:'DELETE'" in js
    assert 'atlasFileCenter' in js
    assert 'confirm(' in js
    assert 'Просмотр' in js
    assert 'Выбрать' in js
