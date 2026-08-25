import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from atlas_browser_jobs import BrowserJobManager


class BrowserJobSessionTests(unittest.IsolatedAsyncioTestCase):
    @patch("atlas_browser_jobs.BrowserExecutor._validate_public_url", return_value="https://example.com")
    async def test_submit_requires_session_store(self, _validate):
        executor = Mock()
        executor.max_actions = 40
        executor.ALLOWED_ACTIONS = {"wait"}
        executor.session_store = None
        executor._validate_public_url.return_value = "https://example.com"
        manager = BrowserJobManager(executor=executor)
        with self.assertRaisesRegex(ValueError, "browser_session_store_not_configured"):
            await manager.submit("https://example.com", [{"type": "wait"}], session_name="shopify")

    async def test_worker_passes_session_options(self):
        executor = Mock()
        executor.max_actions = 40
        executor.ALLOWED_ACTIONS = {"wait"}
        executor.session_store = object()
        executor._validate_public_url.return_value = "https://example.com"
        result = Mock(ok=True, error=None)
        result.public.return_value = {"ok": True}
        executor.run = AsyncMock(return_value=result)
        manager = BrowserJobManager(executor=executor)
        job = await manager.submit(
            "https://example.com",
            [{"type": "wait", "ms": 1}],
            session_name="shopify",
            save_session=True,
        )
        await asyncio.wait_for(manager.queue.join(), timeout=2)
        self.assertEqual(manager.get(job.id).status, "done")
        executor.run.assert_awaited_once_with(
            start_url="https://example.com",
            actions=[{"type": "wait", "ms": 1}],
            session_name="shopify",
            save_session=True,
        )
        await manager.stop()


if __name__ == "__main__":
    unittest.main()
