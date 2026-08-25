import unittest
from unittest.mock import AsyncMock, Mock

from atlas_autonomy_workers import AutonomyWorkers


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_worker_waits_for_result(self):
        manager = Mock()
        submitted = Mock(id="j1")
        manager.submit = AsyncMock(return_value=submitted)
        finished = Mock(status="done", result={"ok": True, "url": "https://example.com"}, error=None)
        manager.get.return_value = finished
        worker = AutonomyWorkers(browser=manager)
        result = await worker.browser_worker({"start_url": "https://example.com", "actions": []})
        self.assertTrue(result["ok"])

    async def test_verify_worker_rejects_bad_result(self):
        worker = AutonomyWorkers()
        with self.assertRaises(AssertionError):
            await worker.verify_worker({"value": "abc", "checks": [{"type": "contains", "expected": "xyz"}]})

    async def test_approval_blocks_graph(self):
        worker = AutonomyWorkers()
        result = await worker.approval_worker({"reason": "payment", "summary": "Pay invoice"})
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "payment")


if __name__ == "__main__":
    unittest.main()
