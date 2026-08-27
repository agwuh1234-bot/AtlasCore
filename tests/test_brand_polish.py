import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrandPolishTests(unittest.TestCase):
    def test_brand_polish_asset_is_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/brand-polish.css', html)
        self.assertLess(html.index('/app/reference-icons.css'), html.index('/app/brand-polish.css'))
        self.assertLess(html.index('/app/brand-polish.css'), html.index('/app/control-icons.css'))

    def test_brand_matches_atlas_pro_reference_without_user_identity(self):
        css = (ROOT / "web" / "brand-polish.css").read_text(encoding="utf-8")
        self.assertIn("content:'A'", css)
        self.assertIn("content:'PRO'", css)
        self.assertIn('.ref-brand-status', css)
        self.assertIn('#45dda1', css)
        self.assertNotIn('@', css)


if __name__ == '__main__':
    unittest.main()
