import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import atlas_n8n_ecom_run as run_gate


SAFE_WORKFLOW = {
    "nodes": [
        {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "parameters": {}},
        {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "parameters": {}},
        {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
        {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
        {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
        {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
        {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True, "parameters": {}},
    ],
    "connections": {
        "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]},
        "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
        "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
    },
    "active": False,
}


class EcomRunGateTests(unittest.IsolatedAsyncioTestCase):
    def test_readiness_accepts_only_safe_inactive_topology(self):
        readiness = run_gate.execution_readiness(SAFE_WORKFLOW)
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["issues"], [])
        self.assertFalse(readiness["active"])

    def test_readiness_blocks_active_workflow(self):
        workflow = dict(SAFE_WORKFLOW)
        workflow["active"] = True
        readiness = run_gate.execution_readiness(workflow)
        self.assertFalse(readiness["ready"])
        self.assertIn("workflow_active", readiness["issues"])

    async def test_run_flag_off_never_touches_n8n(self):
        logger = MagicMock()
        with patch.dict(os.environ, {run_gate.RUN_FLAG: ""}, clear=False), \
             patch.object(run_gate, "call_tool", new=AsyncMock()) as call_tool:
            result = await run_gate.maybe_run_ecomsx222_safe(logger)
        self.assertEqual(result["reason"], "run_flag_disabled")
        call_tool.assert_not_awaited()

    async def test_write_policy_block_never_touches_n8n(self):
        logger = MagicMock()
        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(False, "writes_disabled")), \
             patch.object(run_gate, "call_tool", new=AsyncMock()) as call_tool:
            result = await run_gate.maybe_run_ecomsx222_safe(logger)
        self.assertEqual(result["reason"], "writes_disabled")
        call_tool.assert_not_awaited()

    async def test_safety_failure_blocks_execute(self):
        logger = MagicMock()
        unsafe = dict(SAFE_WORKFLOW)
        unsafe["active"] = True
        details_result = type("Result", (), {"structuredContent": unsafe, "content": []})()
        call_tool = AsyncMock(return_value=details_result)

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertEqual(result["reason"], "safety_check_failed")
        self.assertEqual(call_tool.await_count, 1)
        self.assertEqual(call_tool.await_args_list[0].args[0], "get_workflow_details")

    async def test_safe_run_rechecks_details_before_execute(self):
        logger = MagicMock()
        details_result = type("Result", (), {"structuredContent": SAFE_WORKFLOW, "content": []})()
        execute_result = type("Result", (), {"structuredContent": {"executionId": "redacted"}, "content": []})()
        call_tool = AsyncMock(side_effect=[details_result, execute_result])

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertTrue(result["executed"])
        self.assertEqual(call_tool.await_count, 2)
        self.assertEqual(call_tool.await_args_list[0].args[0], "get_workflow_details")
        self.assertEqual(call_tool.await_args_list[1].args[0], run_gate.EXECUTE_TOOL)


if __name__ == "__main__":
    unittest.main()
