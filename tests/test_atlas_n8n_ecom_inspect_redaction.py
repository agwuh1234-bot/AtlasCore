import unittest

from atlas_n8n_ecom import _safe_params


class EcomInspectRedactionTests(unittest.TestCase):
    def test_http_url_query_credentials_are_redacted(self):
        node = {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": "GET",
                "url": "https://example.test/hook?token=super-secret&mode=test&x-amz-signature=abcdef",
            },
        }

        safe = _safe_params(node)

        self.assertNotIn("super-secret", safe["url"])
        self.assertNotIn("abcdef", safe["url"])
        self.assertIn("token=<redacted>", safe["url"])
        self.assertIn("x-amz-signature=<redacted>", safe["url"])
        self.assertIn("mode=test", safe["url"])

    def test_http_url_userinfo_credentials_are_redacted(self):
        node = {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "url": "https://alice:very-secret@example.test/path",
            },
        }

        safe = _safe_params(node)

        self.assertNotIn("alice", safe["url"])
        self.assertNotIn("very-secret", safe["url"])
        self.assertIn("https://<redacted>@example.test/path", safe["url"])

    def test_benign_http_metadata_is_preserved(self):
        node = {
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": "POST",
                "url": "https://api.example.test/v1/items?mode=test",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "githubApi",
                "sendBody": True,
            },
        }

        safe = _safe_params(node)

        self.assertEqual(safe["method"], "POST")
        self.assertEqual(safe["url"], "https://api.example.test/v1/items?mode=test")
        self.assertEqual(safe["authentication"], "predefinedCredentialType")
        self.assertEqual(safe["nodeCredentialType"], "githubApi")
        self.assertIs(safe["sendBody"], True)


if __name__ == "__main__":
    unittest.main()
