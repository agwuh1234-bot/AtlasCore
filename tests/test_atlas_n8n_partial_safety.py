import os
import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n


class N8NPartialWorkflowSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_alternate_partial_workflow_tool_is_recognized(self):
        self.assertTrue(atlas_n8n._is_partial_workflow_tool("update_workflow"))
        self.assertTrue(atlas_n8n._is_partial_workflow_tool("n8n_update_partial_workflow"))
        self.assertFalse(atlas_n8n._is_partial_workflow_tool("get_workflow"))

    def test_topology_rewrites_and_deactivation_are_destructive(self):
        for op_type in (
            "disableNode",
            "deactivateWorkflow",
            "replaceConnections",
            "rewireConnection",
            "cleanStaleConnections",
        ):
            with self.subTest(op_type=op_type):
                self.assertTrue(
                    atlas_n8n._contains_destructive_workflow_operation(
                        {"operations": [{"type": op_type}]}
                    )
                )

    def test_reviewed_non_destructive_operations_remain_normal_writes(self):
        for op_type in (
            "addNode",
            "updateNode",
            "updateNodeParameters",
            "addConnection",
        ):
            with self.subTest(op_type=op_type):
                self.assertFalse(
                    atlas_n8n._contains_destructive_workflow_operation(
                        {"operations": [{"type": op_type}]}
                    )
                )
        self.assertFalse(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{"type": "setNodeDisabled", "disabled": False}]}
            )
        )

    def test_unknown_or_malformed_operations_fail_closed(self):
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{"type": "futureVendorOperation"}]}
            )
        )
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{}]}
            )
        )
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": ["addNode"]}
            )
        )
        self.assertTrue(
            atlas_n8n._contains_destructive_workflow_operation(
                {"operations": [{"type": "setNodeDisabled"}]}
            )
        )

    async def test_unknown_partial_operation_requires_destructive_opt_in(self):
        tool = type("Tool", (), {"name": "update_workflow", "inputSchema": {"type": "object"}})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {
            "workflowId": "wf_1",
            "operations": [{"type": "futureVendorOperation"}],
        }
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(
            atlas_n8n, "n8n_session", return_value=FakeContext()
        ):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "destructive_disabled"):
                await atlas_n8n.call_tool("update_workflow", arguments)

        session.call_tool.assert_not_awaited()

    async def test_alternate_partial_tool_requires_destructive_opt_in(self):
        tool = type("Tool", (), {"name": "n8n_update_partial_workflow", "inputSchema": {"type": "object"}})()
        session = AsyncMock()
        session.list_tools.return_value = type("Result", (), {"tools": [tool]})()

        class FakeContext:
            async def __aenter__(self):
                return session
            async def __aexit__(self, exc_type, exc, tb):
                return False

        arguments = {
            "id": "wf_1",
            "operations": [{"type": "deactivateWorkflow"}],
        }
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true"}, clear=False), patch.object(
            atlas_n8n, "n8n_session", return_value=FakeContext()
        ):
            os.environ.pop("N8N_DESTRUCTIVE_ENABLED", None)
            with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "destructive_disabled"):
                await atlas_n8n.call_tool("n8n_update_partial_workflow", arguments)

        session.call_tool.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
