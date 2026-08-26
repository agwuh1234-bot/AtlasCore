import os
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import atlas_n8n_ecom_run as run_gate
from tests.test_atlas_n8n_ecom_run import SAFE_WORKFLOW


def result(payload, *, is_error=False):
    return type(
        "Result",
        (),
        {"structuredContent": payload, "content": [], "isError": is_error},
    )()


class EcomRunToolErrorTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, side_effect):
        logger = MagicMock()
        call_tool = AsyncMock(side_effect=side_effect)
        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            value = await run_gate.maybe_run_ecomsx222_safe(logger)
        return value, call_tool

    async def test_first_preflight_tool_error_blocks_execution(self):
        value, call_tool = await self._run([result(SAFE_WORKFLOW, is_error=True)])
        self.assertFalse(value["executed"])
        self.assertEqual(value["reason"], "preflight_first_read_tool_error")
        self.assertEqual(call_tool.await_count, 1)

    async def test_second_preflight_tool_error_blocks_execution(self):
        value, call_tool = await self._run([
            result(SAFE_WORKFLOW),
            result(deepcopy(SAFE_WORKFLOW), is_error=True),
        ])
        self.assertFalse(value["executed"])
        self.assertEqual(value["reason"], "preflight_second_read_tool_error")
        self.assertEqual(call_tool.await_count, 2)

    async def test_execute_tool_error_cannot_be_confirmed_by_success_like_payload(self):
        value, call_tool = await self._run([
            result(SAFE_WORKFLOW),
            result(deepcopy(SAFE_WORKFLOW)),
            result({"executionId": "123", "status": "success"}, is_error=True),
        ])
        self.assertFalse(value["ok"])
        self.assertTrue(value["executed"])
        self.assertEqual(value["reason"], "execution_tool_error")
        self.assertEqual(call_tool.await_count, 3)


if __name__ == "__main__":
    unittest.main()
