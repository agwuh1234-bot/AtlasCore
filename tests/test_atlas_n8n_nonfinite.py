import math
import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n


class N8NNonFiniteNumberTests(unittest.IsolatedAsyncioTestCase):
    async def _assert_blocked(self, value):
        tool = type(
            "Tool",
            (),
            {
                "name": "workflow_test",
                "inputSchema": {
                    "type": "object",
                    "properties": {"limit": {"type": "number", "minimum": 0}},
                },
            },
        )()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "finite number"):
                await atlas_n8n.call_tool("workflow_test", {"limit": value})
        session.call_tool.assert_not_awaited()

    async def test_nan_is_blocked_before_mcp_call(self):
        await self._assert_blocked(float("nan"))

    async def test_positive_infinity_is_blocked_before_mcp_call(self):
        await self._assert_blocked(float("inf"))

    async def test_negative_infinity_is_blocked_before_mcp_call(self):
        await self._assert_blocked(float("-inf"))


if __name__ == "__main__":
    unittest.main()
