import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectSwitcherLiveTests(unittest.TestCase):
    def test_project_switcher_assets_load_before_legacy_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/project-switcher-live.css', html)
        self.assertIn('/app/project-switcher-live.js', html)
        self.assertLess(html.index('/app/project-switcher-live.js'), html.index('/app/ui-actions.js'))

    def test_switcher_reads_and_creates_real_projects(self):
        source = (ROOT / "web" / "project-switcher-live.js").read_text(encoding="utf-8")
        self.assertIn("json('/app-projects')", source)
        self.assertIn("method:'POST'", source)
        self.assertIn("JSON.stringify({name})", source)
        self.assertIn("atlas_active_project_id", source)
        self.assertIn("location.reload()", source)

    def test_header_and_sidebar_project_buttons_are_intercepted(self):
        source = (ROOT / "web" / "project-switcher-live.js").read_text(encoding="utf-8")
        self.assertIn(".atlas-project-switch", source)
        self.assertIn("Проекты", source)
        self.assertIn("stopImmediatePropagation", source)


if __name__ == "__main__":
    unittest.main()
