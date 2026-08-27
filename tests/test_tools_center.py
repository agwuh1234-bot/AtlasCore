import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolsCenterTests(unittest.TestCase):
    def test_tool_center_assets_load_before_legacy_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/tools-center.css', html)
        self.assertIn('/app/tools-center.js', html)
        self.assertLess(html.index('/app/tools-center.js'), html.index('/app/ui-actions.js'))

    def test_builtin_tools_open_real_studios(self):
        source = (ROOT / "web" / "tools-center.js").read_text(encoding="utf-8")
        for api in ('AtlasCodeStudio', 'AtlasVideoStudio', 'AtlasShopifyStudio', 'AtlasAutomationStudio'):
            self.assertIn(api, source)
        self.assertIn("AtlasStudios?.open?.('files')", source)
        self.assertIn("/app-integrations/status", source)
        self.assertIn(".dash-tool-card.add", source)
        self.assertIn("Инструменты", source)

    def test_custom_tools_are_project_scoped(self):
        source = (ROOT / "web" / "tools-center.js").read_text(encoding="utf-8")
        self.assertIn("atlas_active_project_id", source)
        self.assertIn("atlas_custom_tools:${project()}", source)
        self.assertIn("localStorage.setItem(key()", source)
        self.assertIn("Запустить", source)


if __name__ == "__main__":
    unittest.main()
