import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplatesCenterTests(unittest.TestCase):
    def test_templates_assets_intercept_before_legacy_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/templates-center.css', html)
        self.assertIn('/app/templates-center.js', html)
        self.assertLess(html.index('/app/templates-center.js'), html.index('/app/ui-actions.js'))

    def test_presets_route_to_real_studios(self):
        source = (ROOT / "web" / "templates-center.js").read_text(encoding="utf-8")
        for api in (
            'AtlasVideoStudio',
            'AtlasShopifyStudio',
            'AtlasCodeStudio',
            "AtlasStudios?.open?.('files')",
            'AtlasAutomationStudio',
        ):
            self.assertIn(api, source)
        for title in (
            'UGC реклама',
            'Reels / TikTok',
            'Shopify Product Page',
            'CRO аудит магазина',
            'Code Review',
            'Анализ файлов',
            'n8n Workflow',
            'План проекта',
        ):
            self.assertIn(title, source)

    def test_custom_templates_are_scoped_to_current_project(self):
        source = (ROOT / "web" / "templates-center.js").read_text(encoding="utf-8")
        self.assertIn("atlas_active_project_id", source)
        self.assertIn("atlas_custom_templates:${project()}", source)
        self.assertIn("localStorage.setItem(storageKey()", source)


if __name__ == "__main__":
    unittest.main()
