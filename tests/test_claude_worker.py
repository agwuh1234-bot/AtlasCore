import unittest

from atlas_claude_worker import ClaudeWorker


class ClaudeWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_key_blocks_without_network(self):
        worker = ClaudeWorker(api_key="")
        result = await worker({"task": "review code"})
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "anthropic_api_key_required")

    async def test_empty_task_is_rejected_when_configured(self):
        worker = ClaudeWorker(api_key="test-key")
        with self.assertRaises(ValueError):
            await worker({"task": ""})

    def test_configured_flag(self):
        self.assertTrue(ClaudeWorker(api_key="x").configured)
        self.assertFalse(ClaudeWorker(api_key="").configured)


if __name__ == "__main__":
    unittest.main()
