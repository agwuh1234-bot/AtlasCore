import os
import unittest
from pathlib import Path
from unittest.mock import patch

from atlas_integrations_status_api import _railway_runtime, _shopify_direct_configured


ROOT = Path(__file__).resolve().parents[1]


class IntegrationsCenterTests(unittest.TestCase):
    def test_assets_load_and_interceptor_precedes_legacy_ui_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/integrations-center.css', html)
        self.assertIn('/app/integrations-center.js', html)
        self.assertLess(
            html.index('/app/integrations-center.js'),
            html.index('/app/ui-actions.js'),
        )

    def test_status_api_never_returns_secret_values(self):
        source = (ROOT / "atlas_integrations_status_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/status")', source)
        self.assertNotIn('@router.post(', source)
        self.assertNotIn('@router.put(', source)
        self.assertNotIn('@router.delete(', source)
        self.assertNotIn('os.environ.items()', source)

    def test_railway_runtime_exposes_only_non_secret_labels(self):
        with patch.dict(
            os.environ,
            {
                "RAILWAY_PROJECT_ID": "private-project-id",
                "RAILWAY_SERVICE_ID": "private-service-id",
                "RAILWAY_SERVICE_NAME": "AtlasCore",
                "RAILWAY_ENVIRONMENT_NAME": "production",
            },
            clear=False,
        ):
            value = _railway_runtime()
        self.assertTrue(value["running"])
        self.assertEqual(value["service"], "AtlasCore")
        self.assertEqual(value["environment"], "production")
        self.assertNotIn("private-project-id", repr(value))
        self.assertNotIn("private-service-id", repr(value))

    def test_shopify_status_is_coarse_boolean_only(self):
        with patch.dict(os.environ, {"SHOPIFY_ACCESS_TOKEN": "shpat_private"}, clear=False):
            self.assertTrue(_shopify_direct_configured())

    def test_buttons_open_real_studios_or_real_status_actions(self):
        source = (ROOT / "web" / "integrations-center.js").read_text(encoding="utf-8")
        self.assertIn('window.AtlasShopifyStudio?.open?.()', source)
        self.assertIn('window.AtlasCodeStudio?.open?.()', source)
        self.assertIn('window.AtlasAutomationStudio?.open?.()', source)
        self.assertIn("get('/app-code/status')", source)
        self.assertIn("get('/app-automation/status')", source)
        self.assertIn("get('/health')", source)
        self.assertIn('.ref-nav-item,.dash-side-nav-item', source)


if __name__ == "__main__":
    unittest.main()
