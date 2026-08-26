import os
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import atlas_n8n_ecom_run as run_gate
from tests.test_atlas_n8n_ecom_run import SAFE_WORKFLOW, result


class EcomRunExecutionExceptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_exception_is_marked_as_attempted(self):
        logger = MagicMock()
        call_tool = AsyncMock(
            side_effect=[
                result(SAFE_WORKFLOW),
                result(deepcopy(SAFE_WORKFLOW)),
                TimeoutError("ambiguous transport failure"),
            ]
        )

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertFalse(result_value["ok"])
        self.assertTrue(result_value["executed"])
        self.assertEqual(result_value["reason"], "execution_exception")
        self.assertEqual(call_tool.await_count, 3)

    async def test_preflight_exception_is_not_marked_as_executed(self):
        logger = MagicMock()
        call_tool = AsyncMock(side_effect=TimeoutError("preflight failed"))

        with patch.dict(os.environ, {run_gate.RUN_FLAG: "1"}, clear=False), \
             patch.object(run_gate, "configured", return_value=True), \
             patch.object(run_gate, "decision", return_value=(True, "ok")), \
             patch.object(run_gate, "call_tool", new=call_tool):
            result_value = await run_gate.maybe_run_ecomsx222_safe(logger)

        self.assertFalse(result_value["ok"])
        self.assertFalse(result_value["executed"])
        self.assertEqual(result_value["reason"], "TimeoutError")
        self.assertEqual(call_tool.await_count, 1)


if __name__ == "__main__":
    unittest.main()
