import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n


class N8NArgumentSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_tool_uses_deep_snapshot_of_arguments(self):
        tool = type(
            "Tool",
            (),
            {
                "name": "workflow_test",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "payload": {"type": "object"},
                    },
                },
            },
        )()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()
        session.call_tool.return_value = object()

        class FakeContext:
            async def __aenter__(self):
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {"payload": {"mode": "safe", "items": [1, 2]}}
        original_nested = arguments["payload"]

        async def capture_call(name, payload):
            self.assertIsNot(payload, arguments)
            self.assertIsNot(payload["payload"], original_nested)
            arguments["payload"]["mode"] = "mutated"
            arguments["payload"]["items"].append(3)
            self.assertEqual(payload, {"payload": {"mode": "safe", "items": [1, 2]}})
            return object()

        session.call_tool.side_effect = capture_call

        with patch.dict("os.environ", {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(
            atlas_n8n, "n8n_session", return_value=FakeContext()
        ):
            await atlas_n8n.call_tool("workflow_test", arguments)

        session.call_tool.assert_awaited_once()

    async def test_call_tool_fails_before_connecting_when_snapshot_is_impossible(self):
        class BadCopy:
            def __deepcopy__(self, memo):
                raise RuntimeError("copy blocked")

        with patch.object(atlas_n8n, "n8n_session") as mocked_session:
            with self.assertRaisesRegex(
                atlas_n8n.N8NBridgeError, "could not be safely snapshotted"
            ):
                await atlas_n8n.call_tool("workflow_test", {"payload": BadCopy()})

        mocked_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
