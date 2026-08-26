import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n


class N8NArgumentSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_caller_mutation_after_start_cannot_change_executed_arguments(self):
        tool = type("Tool", (), {"name": "update_workflow", "inputSchema": {"type": "object"}})()
        discovery_started = asyncio.Event()
        allow_discovery = asyncio.Event()

        session = AsyncMock()

        async def delayed_list_tools():
            discovery_started.set()
            await allow_discovery.wait()
            return type("Result", (), {"tools": [tool]})()

        session.list_tools.side_effect = delayed_list_tools
        session.call_tool.return_value = object()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {
            "workflowId": "1",
            "operations": [{"type": "addNode", "node": {"name": "Safe"}}],
        }

        with patch.dict(
            os.environ,
            {"N8N_WRITES_ENABLED": "true", "N8N_DESTRUCTIVE_ENABLED": "false"},
            clear=False,
        ), patch.object(atlas_n8n, "n8n_session", return_value=FakeContext()):
            task = asyncio.create_task(atlas_n8n.call_tool("update_workflow", arguments))
            await discovery_started.wait()

            arguments["operations"][0]["type"] = "removeNode"
            arguments["operations"][0]["node"]["name"] = "Mutated"
            allow_discovery.set()
            await task

        session.call_tool.assert_awaited_once_with(
            "update_workflow",
            {
                "workflowId": "1",
                "operations": [{"type": "addNode", "node": {"name": "Safe"}}],
            },
        )

    async def test_unsnapshotable_arguments_fail_before_connecting(self):
        class BadCopy:
            def __deepcopy__(self, memo):
                raise RuntimeError("no copy")

        arguments = {"value": BadCopy()}
        with patch.object(atlas_n8n, "n8n_session") as mocked_session:
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "safely snapshotted"):
                await atlas_n8n.call_tool("workflow_test", arguments)
        mocked_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
