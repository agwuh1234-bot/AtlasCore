from pathlib import Path
import unittest

from fastapi import HTTPException

from atlas_code_api import _safe_path


ROOT = Path(__file__).resolve().parents[1]


class CodeStudioLiveTests(unittest.TestCase):
    def test_code_studio_assets_are_loaded_before_legacy_studio_panels(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/app/code-studio-live.css", html)
        self.assertIn("/app/code-studio-live.js", html)
        self.assertLess(
            html.index("/app/code-studio-live.js"),
            html.index("/app/studio-panels.js"),
        )

    def test_code_studio_uses_authenticated_read_only_routes(self):
        source = (ROOT / "atlas_code_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/app-code/tree")', source)
        self.assertIn('@router.get("/app-code/file")', source)
        self.assertIn('@router.get("/app-code/recent-diff")', source)
        self.assertIn('@router.get("/app-code/status")', source)
        self.assertNotIn("@router.post", source)
        self.assertNotIn("@router.put", source)
        self.assertNotIn("@router.delete", source)

    def test_code_studio_mutations_stay_behind_atlas_confirmation_and_developer_mode(self):
        source = (ROOT / "web" / "code-studio-live.js").read_text(encoding="utf-8")
        self.assertIn("window.AtlasDialog?.confirm", source)
        self.assertIn("title:'Применить изменение?'", source)
        self.assertIn("writeModeBtn", source)
        self.assertIn("Текущий SHA файла", source)
        self.assertIn("не перезаписывай вслепую", source)
        self.assertIn("window.confirm(`Применить изменение", source)

    def test_code_studio_uses_native_atlas_feedback(self):
        source = (ROOT / "web" / "code-studio-live.js").read_text(encoding="utf-8")
        self.assertIn("window.AtlasNotice?.warn", source)
        self.assertIn("window.AtlasNotice?.error", source)
        self.assertIn("window.AtlasNotice?.success", source)
        self.assertNotIn("alert('Сначала выберите файл.')", source)

    def test_safe_path_rejects_parent_traversal(self):
        self.assertEqual(_safe_path("web/app.js"), "web/app.js")
        self.assertEqual(_safe_path("/web//app.js/"), "web/app.js")
        with self.assertRaises(HTTPException):
            _safe_path("../main.py")


if __name__ == "__main__":
    unittest.main()
