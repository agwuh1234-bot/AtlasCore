import unittest
from unittest.mock import AsyncMock, Mock, patch

import atlas_n8n_ecom_repair_gate as gate


class EcomRepairReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_update_exception_can_be_read_back_as_verified(self):
        before = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        after = {"nodes": [{"name": "stable"}, {"name": "repaired"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[before, before, RuntimeError("transport lost after send"), after])
        initial_plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        verified_plan = {"ok": True, "operations": [], "remaining_issues": []}
        logger = Mock()

        with patch.object(gate, "_enabled", return_value=True), \
             patch.object(gate, "configured", return_value=True), \
             patch.object(gate, "decision", return_value=(True, "ok")), \
             patch.object(gate, "call_tool", call), \
             patch.object(gate, "_payload", side_effect=lambda x: x), \
             patch.object(gate, "_workflow_fingerprint", side_effect=lambda value: "before" if value is before else "after"), \
             patch.object(gate, "plan_safe_ecom_repair", side_effect=[initial_plan, initial_plan, verified_plan]):
            result = await gate.maybe_apply_safe_ecom_repair(logger)

        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["reconciled"])
        self.assertEqual(call.await_count, 4)

    async def test_ambiguous_update_reconciliation_never_retries_write(self):
        before = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[before, before, RuntimeError("transport lost after send"), before])
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}

        with patch.object(gate, "_enabled", return_value=True), \
             patch.object(gate, "configured", return_value=True), \
             patch.object(gate, "decision", return_value=(True, "ok")), \
             patch.object(gate, "call_tool", call), \
             patch.object(gate, "_payload", side_effect=lambda x: x), \
             patch.object(gate, "_workflow_fingerprint", return_value="same"), \
             patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(Mock())

        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "repair_update_exception")
        update_calls = [c for c in call.await_args_list if c.args and c.args[0] == gate.UPDATE_TOOL]
        self.assertEqual(len(update_calls), 1)


if __name__ == "__main__":
    unittest.main()
