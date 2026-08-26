import unittest
from unittest.mock import AsyncMock, Mock, patch

import atlas_n8n_ecom_repair_gate as gate


class EcomRepairSecondReadbackTests(unittest.IsolatedAsyncioTestCase):
    def _patches(self, call):
        workflow = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired = {"nodes": [{"name": "repaired"}], "connections": {}, "active": False}
        plan_before = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        plan_after = {"ok": True, "operations": [], "remaining_issues": []}
        fingerprints = iter(["before-fp", "before-fp", "repaired-fp", "repaired-fp"])
        plans = iter([plan_before, plan_before, plan_after, plan_after])
        return workflow, repaired, [
            patch.object(gate, "_enabled", return_value=True),
            patch.object(gate, "configured", return_value=True),
            patch.object(gate, "decision", return_value=(True, "ok")),
            patch.object(gate, "call_tool", call),
            patch.object(gate, "_payload", side_effect=lambda x: x),
            patch.object(gate, "_workflow_fingerprint", side_effect=lambda _: next(fingerprints)),
            patch.object(gate, "plan_safe_ecom_repair", side_effect=lambda _: next(plans)),
        ]

    async def test_second_verification_exception_is_fail_closed(self):
        workflow = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired = {"nodes": [{"name": "repaired"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, repaired, RuntimeError("second verification transport lost")])
        _, _, patches = self._patches(call)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "post_repair_second_verification_exception")
        self.assertEqual(call.await_count, 5)

    async def test_second_verification_tool_error_is_fail_closed(self):
        workflow = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired = {"nodes": [{"name": "repaired"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, repaired, {"isError": True, "content": [{"type": "text", "text": "second verification rejected"}]}])
        _, _, patches = self._patches(call)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "post_repair_second_verification_tool_error")
        self.assertEqual(call.await_count, 5)

    async def test_changed_second_verification_fingerprint_is_not_verified(self):
        workflow = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired_a = {"nodes": [{"name": "repaired-a"}], "connections": {}, "active": False}
        repaired_b = {"nodes": [{"name": "repaired-b"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, repaired_a, repaired_b])
        plan_before = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        plan_after = {"ok": True, "operations": [], "remaining_issues": []}
        fingerprints = iter(["before-fp", "before-fp", "repaired-a-fp", "repaired-b-fp"])
        plans = iter([plan_before, plan_before, plan_after, plan_after])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", side_effect=lambda _: next(fingerprints)), patch.object(gate, "plan_safe_ecom_repair", side_effect=lambda _: next(plans)):
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "post_repair_verification_changed")
        self.assertEqual(call.await_count, 5)


if __name__ == "__main__":
    unittest.main()
