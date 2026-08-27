import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrandHealthTests(unittest.TestCase):
    def test_sidebar_presence_uses_live_service_status(self):
        source = (ROOT / "web" / "brand-health.js").read_text(encoding="utf-8")
        self.assertIn("#serviceStatus", source)
        self.assertIn("MutationObserver", source)
        self.assertIn("AtlasBrandHealth", source)
        self.assertIn("online", source)
        self.assertIn("offline", source)

    def test_brand_health_assets_are_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/brand-health.css', html)
        self.assertIn('/app/brand-health.js', html)


if __name__ == "__main__":
    unittest.main()
