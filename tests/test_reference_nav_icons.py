import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReferenceNavIconTests(unittest.TestCase):
    def test_reference_navigation_uses_svg_paths_not_unicode_glyphs(self):
        source = (ROOT / "web" / "reference-v2.js").read_text(encoding="utf-8")
        self.assertIn("const ICONS=", source)
        self.assertIn("createElementNS", source)
        for icon in ("home", "chat", "projects", "tools", "file", "templates", "integrations", "settings"):
            self.assertIn(f"'{icon}'", source)
        self.assertNotIn("navButton('Главная','⌂'", source)
        self.assertNotIn("navButton('Настройки','⚙'", source)

    def test_icon_styles_are_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "reference-icons.css").read_text(encoding="utf-8")
        self.assertIn('/app/reference-icons.css', html)
        self.assertIn('.ref-nav-icon svg', css)
        self.assertIn('stroke:currentColor', css)


if __name__ == "__main__":
    unittest.main()
