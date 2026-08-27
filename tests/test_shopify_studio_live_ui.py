from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class ShopifyStudioLiveUITests(unittest.TestCase):
    def test_assets_are_loaded_before_legacy_studio_panels(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/shopify-studio-live.css', html)
        self.assertIn('/app/shopify-studio-live.js', html)
        self.assertLess(
            html.index('/app/shopify-studio-live.js'),
            html.index('/app/studio-panels.js'),
        )

    def test_page_builder_has_live_preview_and_useful_actions(self):
        js = (WEB / "shopify-studio-live.js").read_text(encoding="utf-8")
        for marker in (
            'Product Page Builder',
            'Live preview',
            'CRO аудит',
            'SEO',
            'Проверить claims',
            'Подготовить изменения Shopify',
            'Export JSON',
            'atlas_shopify_draft:',
            'window.AtlasShopifyStudio',
        ):
            self.assertIn(marker, js)

    def test_publish_remains_confirmation_gated(self):
        js = (WEB / "shopify-studio-live.js").read_text(encoding="utf-8")
        self.assertIn('Ничего не публикуй и не удаляй без отдельного подтверждения', js)
        self.assertIn('Publish/delete не выполняются этой кнопкой', js)
        self.assertNotIn("fetch('/shopify/publish", js)


if __name__ == '__main__':
    unittest.main()
