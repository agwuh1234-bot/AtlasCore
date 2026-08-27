import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavStateModeTests(unittest.TestCase):
    def test_home_and_chat_are_distinct_actions(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("function home()", source)
        self.assertIn("function chat()", source)
        self.assertIn("atlas_dashboard_view", source)
        self.assertIn("atlas-chat-focus", source)
        self.assertIn("'Главная':home", source)
        self.assertIn("'Чат':chat", source)

    def test_navigation_routes_to_live_centers(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("AtlasToolsCenter", source)
        self.assertIn("AtlasTemplates", source)
        self.assertIn("AtlasIntegrations", source)
        self.assertIn("tapTab('projects')", source)
        self.assertIn("tapTab('files')", source)

    def test_focus_chat_css_removes_dashboard_noise(self):
        css = (ROOT / "web" / "nav-state.css").read_text(encoding="utf-8")
        self.assertIn("body.atlas-chat-focus .atlas-dashboard-right", css)
        self.assertIn("body.atlas-chat-focus .atlas-tool-strip", css)
        self.assertIn("grid-template-columns:minmax(0,1fr)", css)

    def test_focus_styles_are_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/nav-state.css', html)
        self.assertIn('/app/nav-state.js', html)


if __name__ == "__main__":
    unittest.main()
