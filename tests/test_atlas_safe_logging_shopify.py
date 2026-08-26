import unittest

from atlas_safe_logging import sanitize_for_log


class ShopifySecretLoggingTests(unittest.TestCase):
    def test_shopify_provider_tokens_are_redacted_without_labels(self):
        samples = [
            "shopify shpat_abcdefghijklmnopqrstuvwx connected",
            "legacy shpca_abcdefghijklmnopqrstuvwx value",
            "legacy shppa_abcdefghijklmnopqrstuvwx value",
            "legacy shpss_abcdefghijklmnopqrstuvwx value",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                safe = sanitize_for_log(sample)
                self.assertIn("<redacted-secret>", safe)
                self.assertNotIn("abcdefghijklmnopqrstuvwx", safe)

    def test_benign_shopify_identifiers_are_preserved(self):
        safe = sanitize_for_log("store=z1egtm-1t.myshopify.com plan=Basic currency=EUR")
        self.assertIn("z1egtm-1t.myshopify.com", safe)
        self.assertIn("Basic", safe)
        self.assertIn("EUR", safe)

    def test_basic_auth_prose_is_not_redacted(self):
        safe = sanitize_for_log("Basic auth enabled for the Shopify admin client")
        self.assertEqual(safe, "Basic auth enabled for the Shopify admin client")

    def test_real_basic_auth_value_is_redacted(self):
        safe = sanitize_for_log("Basic dXNlcjpwYXNzd29yZA==")
        self.assertEqual(safe, "Basic <redacted>")


if __name__ == "__main__":
    unittest.main()
