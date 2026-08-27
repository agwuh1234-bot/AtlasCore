from pathlib import Path

import pytest
from fastapi import HTTPException

from atlas_code_api import _safe_path


ROOT = Path(__file__).resolve().parents[1]


def test_code_studio_assets_are_loaded_before_legacy_studio_panels():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "/app/code-studio-live.css" in html
    assert "/app/code-studio-live.js" in html
    assert html.index("/app/code-studio-live.js") < html.index("/app/studio-panels.js")


def test_code_studio_uses_authenticated_read_only_routes():
    source = (ROOT / "atlas_code_api.py").read_text(encoding="utf-8")
    assert '@router.get("/app-code/tree")' in source
    assert '@router.get("/app-code/file")' in source
    assert '@router.get("/app-code/recent-diff")' in source
    assert '@router.get("/app-code/status")' in source
    assert "@router.post" not in source
    assert "@router.put" not in source
    assert "@router.delete" not in source


def test_code_studio_mutations_stay_behind_developer_mode_confirmation():
    source = (ROOT / "web" / "code-studio-live.js").read_text(encoding="utf-8")
    assert "confirm(`Применить изменение" in source
    assert "writeModeBtn" in source
    assert "Текущий SHA файла" in source
    assert "не перезаписывай вслепую" in source


def test_safe_path_rejects_parent_traversal():
    assert _safe_path("web/app.js") == "web/app.js"
    assert _safe_path("/web//app.js/") == "web/app.js"
    with pytest.raises(HTTPException):
        _safe_path("../main.py")
