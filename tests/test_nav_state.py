import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavStateTests(unittest.TestCase):
    def test_nav_state_asset_is_loaded_after_reference_shell(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/nav-state.js', html)
        self.assertLess(html.index('/app/reference-v2.js'), html.index('/app/nav-state.js'))
        self.assertLess(html.index('/app/nav-state.js'), html.index('/app/integrations-center.js'))

    def test_nav_state_tracks_real_tabs_and_studios(self):
        source = (ROOT / "web" / "nav-state.js").read_text(encoding="utf-8")
        self.assertIn("projects:'Проекты'", source)
        self.assertIn("files:'Файлы'", source)
        self.assertIn("plugins:'Интеграции'", source)
        self.assertIn(".dash-tool-card", source)
        self.assertIn("setActive('Инструменты')", source)
        self.assertIn("aria-current", source)


if __name__ == '__main__':
    unittest.main()
