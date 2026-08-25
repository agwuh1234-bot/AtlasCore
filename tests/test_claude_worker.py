import unittest
from unittest.mock import AsyncMock, patch

from atlas_claude_worker import ClaudeWorker


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "claude-test",
            "content": [{"type": "text", "text": "Review complete"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }


class ClaudeWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_key_blocks_without_network(self):
        worker = ClaudeWorker(api_key="")
        result = await worker({"prompt": "review"})
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "anthropic_api_key_required")

    async def test_empty_prompt_rejected(self):
        worker = ClaudeWorker(api_key="test")
        with self.assertRaises(ValueError):
            await worker({"prompt": " "})

    @patch("atlas_claude_worker.httpx.AsyncClient")
    async def test_returns_review_text(self, client_cls):
        client = AsyncMock()
        client.post.return_value = _Response()
        client_cls.return_value.__aenter__.return_value = client
        worker = ClaudeWorker(api_key="test", model="claude-test")
        result = await worker({"prompt": "review this"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "Review complete")
        self.assertEqual(result["usage"]["output_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
