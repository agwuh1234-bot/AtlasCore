import os
import unittest
from copy import deepcopy
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


def result(payload):
    return type("Result", (), {"structuredContent": payload, "content": []})()


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

    def test_readiness_blocks_missing_active_state(self):
        workflow = dict(SAFE_WORKFLOW)
        workflow.pop("active", None)
        readiness = run_gate.execution_readiness(workflow)
        self.assertFalse(readiness["ready"])
        self.assertIn("workflow_active_state_unknown", readiness["issues"])

    def test_readiness_blocks_non_boolean_active_state(self):
        workflow = dict(SAFE_WORKFLOW)
        workflow["active"] = "false"
        readiness = run_gate.execution_readiness(workflow)
        self.assertFalse(readiness["ready"])
        self.assertIn("workflow_active_state_unknown", readiness["issues"])

    def test_fingerprint_is_stable_and_changes_with_body(self):
        first = run_gate._workflow_fingerprint(SAFE_WORKFLOW)
        same = run_gate._workflow_fingerprint(deepcopy(SAFE_WORKFLOW))
        changed = deepcopy(SAFE_WORKFLOW)
        changed["active"] = True
        self.assertEqual(first, same)
        self.assertNotEqual(first, run_gate._workflow_fingerprint(changed))

    def test_execution_receipt_requires_confirmation_signal(self):
        self.assertFalse(run_gate._execution_receipt(None)["confirmed"])
        self.assertFalse(run_gate._execution_receipt({})["confirmed"])
        self.assertTrue(run_gate._execution_receipt({"executionId": "123"})["confirmed"])
        self.assertTrue(run_gate._execution_receipt({"status": "queued"})["confirmed"])
        self.assertFalse(run_gate._execution_receipt({"status": "error"})["confirmed"])

    async def test_run_flag_off_never_touches_n8n(self):
        logger = MagicMock()
        with patch.dict(os.environ, {run_gate.RUN_FLAG: ""}, clear=False), \
             patch.object(run_gate, "call_tool", new=AsyncMock()) as call_tool:
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)
        self.assertEqual(result_value["reason"], "run_flag_disabled")
        call_tool.assert_not_awaited()

    async def test_write_policy_block_never_touches_n8n(self):
        logger = MagicMock()
        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(False, "writes_disabled")), \
             patch.object(run_gate, "call_tool", new=AsyncMock()) as call_tool:
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)
        self.assertEqual(result_value["reason"], "writes_disabled")
        call_tool.assert_not_awaited()

    async def test_safety_failure_blocks_execute(self):
        logger = MagicMock()
        unsafe = dict(SAFE_WORKFLOW)
        unsafe["active"] = True
        call_tool = AsyncMock(return_value=result(unsafe))

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertEqual(result_value["reason"], "safety_check_failed")
        self.assertEqual(call_tool.await_count, 1)
        self.assertEqual(call_tool.await_args_list[0].args[0], "get_workflow_details")

    async def test_concurrent_workflow_change_blocks_execute(self):
        logger = MagicMock()
        changed = deepcopy(SAFE_WORKFLOW)
        changed["nodes"][1]["position"] = [999, 999]
        call_tool = AsyncMock(side_effect=[result(SAFE_WORKFLOW), result(changed)])

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertFalse(result_value["executed"])
        self.assertEqual(result_value["reason"], "preflight_changed")
        self.assertIn("workflow_changed_during_preflight", result_value["issues"])
        self.assertEqual(call_tool.await_count, 2)
        self.assertTrue(all(call.args[0] == "get_workflow_details" for call in call_tool.await_args_list))

    async def test_safe_run_double_checks_identical_details_before_execute(self):
        logger = MagicMock()
        execute_result = result({"executionId": "redacted"})
        call_tool = AsyncMock(side_effect=[result(SAFE_WORKFLOW), result(deepcopy(SAFE_WORKFLOW)), execute_result])

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertTrue(result_value["executed"])
        self.assertEqual(call_tool.await_count, 3)
        self.assertEqual(call_tool.await_args_list[0].args[0], "get_workflow_details")
        self.assertEqual(call_tool.await_args_list[1].args[0], "get_workflow_details")
        self.assertEqual(call_tool.await_args_list[2].args[0], run_gate.EXECUTE_TOOL)

    async def test_ambiguous_execution_result_is_not_reported_as_success(self):
        logger = MagicMock()
        call_tool = AsyncMock(side_effect=[result(SAFE_WORKFLOW), result(deepcopy(SAFE_WORKFLOW)), result({})])

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertFalse(result_value["ok"])
        self.assertTrue(result_value["executed"])
        self.assertEqual(result_value["reason"], "execution_result_unconfirmed")
        self.assertEqual(call_tool.await_count, 3)


if __name__ == "__main__":
    unittest.main()
