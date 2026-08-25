import unittest
from unittest.mock import patch

from atlas_browser_executor import BrowserExecutor, BrowserExecutorError


class BrowserExecutorSafetyTests(unittest.TestCase):
    def test_rejects_non_http_urls(self):
        for url in ("file:///etc/passwd", "ftp://example.com/a", "javascript:alert(1)"):
            with self.assertRaises(BrowserExecutorError):
                BrowserExecutor._validate_public_url(url)

    def test_rejects_localhost(self):
        with self.assertRaises(BrowserExecutorError):
            BrowserExecutor._validate_public_url("http://localhost:8080")

    @patch("atlas_browser_executor.socket.getaddrinfo")
    def test_rejects_private_resolved_address(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("10.0.0.5", 443))]
        with self.assertRaises(BrowserExecutorError):
            BrowserExecutor._validate_public_url("https://example.invalid")

    @patch("atlas_browser_executor.socket.getaddrinfo")
    def test_accepts_public_resolved_address(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        self.assertEqual(
            BrowserExecutor._validate_public_url("https://example.com"),
            "https://example.com",
        )

    def test_action_vocabulary_is_narrow(self):
        self.assertNotIn("eval", BrowserExecutor.ALLOWED_ACTIONS)
        self.assertNotIn("javascript", BrowserExecutor.ALLOWED_ACTIONS)
        self.assertIn("click", BrowserExecutor.ALLOWED_ACTIONS)


if __name__ == "__main__":
    unittest.main()
