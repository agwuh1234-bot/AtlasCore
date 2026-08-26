import unittest
from unittest.mock import AsyncMock, patch

import atlas_n8n_ecom_repair_gate as gate


class EcomRepairGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_flag_off_never_touches_n8n(self):
        with patch.object(gate, "_enabled", return_value=False), patch.object(gate, "call_tool", new=AsyncMock()) as call:
            result = await gate.maybe_apply_safe_ecom_repair(AsyncMock())
        self.assertEqual(result["reason"], "repair_flag_disabled")
        call.assert_not_awaited()

    async def test_destructive_policy_block_never_touches_n8n(self):
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(False, "destructive_disabled")), patch.object(gate, "call_tool", new=AsyncMock()) as call:
            result = await gate.maybe_apply_safe_ecom_repair(AsyncMock())
        self.assertEqual(result["reason"], "destructive_disabled")
        call.assert_not_awaited()

    async def test_concurrent_change_blocks_update(self):
        first = {"nodes": [], "connections": {}, "active": False}
        second = {"nodes": [{"name": "changed"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[first, second])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "plan_safe_ecom_repair", return_value={"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}):
            result = await gate.maybe_apply_safe_ecom_repair(AsyncMock())
        self.assertEqual(result["reason"], "workflow_changed_during_preflight")
        self.assertEqual(call.await_count, 2)


if __name__ == "__main__":
    unittest.main()
