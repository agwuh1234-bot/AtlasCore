import unittest
from unittest.mock import AsyncMock, patch

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
    def test_rejects_embedded_url_credentials(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        for url in (
            "https://user@example.com/private",
            "https://user:password@example.com/private",
        ):
            with self.assertRaises(BrowserExecutorError):
                BrowserExecutor._validate_public_url(url)
        getaddrinfo.assert_not_called()

    @patch("atlas_browser_executor.socket.getaddrinfo")
    def test_accepts_public_resolved_address(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        self.assertEqual(
            BrowserExecutor._validate_public_url("https://example.com"),
            "https://example.com",
        )

    @patch("atlas_browser_executor.socket.getaddrinfo")
    def test_revalidates_actual_page_location_after_redirect(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 80))]
        page = type("Page", (), {"url": "http://127.0.0.1/admin"})()
        with self.assertRaises(BrowserExecutorError):
            BrowserExecutor._validate_page_location(page)

    @patch("atlas_browser_executor.socket.getaddrinfo")
    def test_accepts_actual_public_page_location(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        page = type("Page", (), {"url": "https://example.com/after-click"})()
        self.assertEqual(
            BrowserExecutor._validate_page_location(page),
            "https://example.com/after-click",
        )

    def test_action_vocabulary_is_narrow(self):
        self.assertNotIn("eval", BrowserExecutor.ALLOWED_ACTIONS)
        self.assertNotIn("javascript", BrowserExecutor.ALLOWED_ACTIONS)
        self.assertIn("click", BrowserExecutor.ALLOWED_ACTIONS)


class BrowserRequestGuardTests(unittest.IsolatedAsyncioTestCase):
    @patch("atlas_browser_executor.socket.getaddrinfo")
    async def test_private_http_request_is_aborted_before_network(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 80))]
        route = type("Route", (), {})()
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        request = type("Request", (), {"url": "http://127.0.0.1/admin"})()

        await BrowserExecutor._guard_request(route, request)

        route.abort.assert_awaited_once_with("blockedbyclient")
        route.continue_.assert_not_awaited()

    @patch("atlas_browser_executor.socket.getaddrinfo")
    async def test_embedded_credentials_subrequest_is_aborted_before_dns(self, getaddrinfo):
        route = type("Route", (), {})()
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        request = type(
            "Request",
            (),
            {"url": "https://user:password@example.com/private.js"},
        )()

        await BrowserExecutor._guard_request(route, request)

        getaddrinfo.assert_not_called()
        route.abort.assert_awaited_once_with("blockedbyclient")
        route.continue_.assert_not_awaited()

    @patch("atlas_browser_executor.socket.getaddrinfo")
    async def test_public_http_request_is_allowed(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        route = type("Route", (), {})()
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        request = type("Request", (), {"url": "https://example.com/app.js"})()

        await BrowserExecutor._guard_request(route, request)

        route.continue_.assert_awaited_once_with()
        route.abort.assert_not_awaited()

    async def test_non_http_subresource_does_not_trigger_dns(self):
        route = type("Route", (), {})()
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        request = type("Request", (), {"url": "data:image/png;base64,AAAA"})()

        with patch("atlas_browser_executor.socket.getaddrinfo") as getaddrinfo:
            await BrowserExecutor._guard_request(route, request)

        getaddrinfo.assert_not_called()
        route.continue_.assert_awaited_once_with()
        route.abort.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
