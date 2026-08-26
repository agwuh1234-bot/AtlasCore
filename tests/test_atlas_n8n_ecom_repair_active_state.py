import unittest
from unittest.mock import AsyncMock, Mock, patch

import atlas_n8n_ecom_repair_gate as gate


class EcomRepairActiveStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_workflow_blocks_before_planning_or_update(self):
        workflow = {"nodes": [], "connections": {}, "active": True}
        call = AsyncMock(return_value=workflow)
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "plan_safe_ecom_repair") as planner:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "workflow_not_explicitly_inactive")
        self.assertEqual(call.await_count, 1)
        planner.assert_not_called()

    async def test_missing_active_state_fails_closed(self):
        workflow = {"nodes": [], "connections": {}}
        call = AsyncMock(return_value=workflow)
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "plan_safe_ecom_repair") as planner:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertEqual(result["reason"], "workflow_not_explicitly_inactive")
        planner.assert_not_called()

    async def test_activation_between_preflights_blocks_update(self):
        first = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        second = {"nodes": [{"name": "stable"}], "connections": {}, "active": True}
        plan = {"ok": True, "operations": [{"type": "removeConnection", "source": "A", "target": "B"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[first, second])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "workflow_became_active_during_preflight")
        self.assertEqual(call.await_count, 2)

    async def test_activation_after_update_fails_verification(self):
        inactive = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        active_after = {"nodes": [{"name": "stable"}], "connections": {}, "active": True}
        plan = {"ok": True, "operations": [{"type": "removeConnection", "source": "A", "target": "B"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[inactive, inactive, {"ok": True}, active_after])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "workflow_active_after_repair")
        self.assertEqual(call.await_count, 4)


if __name__ == "__main__":
    unittest.main()
