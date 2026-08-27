import unittest

import atlas_n8n_ecom as ecom


class EcomSafeUrlIntegrationTests(unittest.TestCase):
    def test_http_safe_params_redacts_signed_query_credentials(self):
        node = {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": "GET",
                "url": (
                    "https://example.test/hook?mode=inspect"
                    "&token=super-secret"
                    "&X-Amz-Signature=abcdef123456"
                    "&X-Amz-Credential=AKIAEXAMPLE%2F20260827%2Feu-central-1%2Fs3%2Faws4_request"
                ),
                "authentication": "none",
            },
        }

        safe = ecom._safe_params(node)
        rendered = repr(safe)

        self.assertIn("mode=inspect", rendered)
        self.assertNotIn("super-secret", rendered)
        self.assertNotIn("abcdef123456", rendered)
        self.assertNotIn("AKIAEXAMPLE", rendered)

    def test_http_safe_params_redacts_url_userinfo(self):
        node = {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": "POST",
                "url": "https://atlas-user:atlas-password@example.test/api?status=test",
                "sendBody": True,
            },
        }

        safe = ecom._safe_params(node)
        rendered = repr(safe)

        self.assertIn("status=test", rendered)
        self.assertNotIn("atlas-user", rendered)
        self.assertNotIn("atlas-password", rendered)


if __name__ == "__main__":
    unittest.main()
