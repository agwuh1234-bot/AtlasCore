import unittest
from unittest.mock import AsyncMock, Mock, patch

import atlas_n8n_ecom_repair_gate as gate


class EcomRepairGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_flag_off_never_touches_n8n(self):
        with patch.object(gate, "_enabled", return_value=False), patch.object(gate, "call_tool", new=AsyncMock()) as call:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertEqual(result["reason"], "repair_flag_disabled")
        call.assert_not_awaited()

    async def test_destructive_policy_block_never_touches_n8n(self):
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(False, "destructive_disabled")), patch.object(gate, "call_tool", new=AsyncMock()) as call:
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertEqual(result["reason"], "destructive_disabled")
        call.assert_not_awaited()

    async def test_first_preflight_read_exception_is_fail_closed(self):
        call = AsyncMock(side_effect=RuntimeError("preflight transport lost"))
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "preflight_first_read_exception")
        self.assertEqual(call.await_count, 1)

    async def test_first_preflight_read_tool_error_is_fail_closed(self):
        call = AsyncMock(return_value={"isError": True, "content": [{"type": "text", "text": "read rejected"}]})
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "preflight_first_read_tool_error")
        self.assertEqual(call.await_count, 1)

    async def test_second_preflight_read_exception_is_fail_closed(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, RuntimeError("second preflight transport lost")])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "preflight_second_read_exception")
        self.assertEqual(call.await_count, 2)

    async def test_second_preflight_read_tool_error_is_fail_closed(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, {"isError": True, "content": [{"type": "text", "text": "second read rejected"}]}])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "preflight_second_read_tool_error")
        self.assertEqual(call.await_count, 2)

    async def test_concurrent_change_blocks_update(self):
        first = {"nodes": [], "connections": {}, "active": False}
        second = {"nodes": [{"name": "changed"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[first, second])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "plan_safe_ecom_repair", return_value={"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}):
            result = await gate.maybe_apply_safe_ecom_repair(Mock())
        self.assertEqual(result["reason"], "workflow_changed_during_preflight")
        self.assertEqual(call.await_count, 2)

    async def test_update_exception_is_marked_as_ambiguous_applied(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, workflow, RuntimeError("transport lost after send"), workflow])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "repair_update_exception")
        self.assertEqual(call.await_count, 4)

    async def test_update_tool_error_result_is_ambiguous_applied(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, workflow, {"isError": True, "content": [{"type": "text", "text": "update rejected"}]}, workflow])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "repair_update_tool_error")
        self.assertEqual(call.await_count, 4)

    async def test_ambiguous_repair_requires_two_identical_verified_readbacks(self):
        before = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired = {"nodes": [{"name": "repaired"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[before, before, RuntimeError("transport lost after send"), repaired, repaired])
        logger = Mock()
        fingerprints = iter(["before-fp", "before-fp", "repaired-fp", "repaired-fp"])
        plans = iter([
            {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []},
            {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []},
            {"ok": True, "operations": [], "remaining_issues": []},
            {"ok": True, "operations": [], "remaining_issues": []},
        ])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", side_effect=lambda _: next(fingerprints)), patch.object(gate, "plan_safe_ecom_repair", side_effect=lambda _: next(plans)):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["reconciled"])
        self.assertEqual(call.await_count, 5)

    async def test_ambiguous_repair_changed_between_readbacks_is_not_verified(self):
        before = {"nodes": [{"name": "before"}], "connections": {}, "active": False}
        repaired_a = {"nodes": [{"name": "repaired-a"}], "connections": {}, "active": False}
        repaired_b = {"nodes": [{"name": "repaired-b"}], "connections": {}, "active": False}
        call = AsyncMock(side_effect=[before, before, RuntimeError("transport lost after send"), repaired_a, repaired_b])
        logger = Mock()
        fingerprints = iter(["before-fp", "before-fp", "repaired-a-fp", "repaired-b-fp"])
        plans = iter([
            {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []},
            {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []},
            {"ok": True, "operations": [], "remaining_issues": []},
            {"ok": True, "operations": [], "remaining_issues": []},
        ])
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", side_effect=lambda _: next(fingerprints)), patch.object(gate, "plan_safe_ecom_repair", side_effect=lambda _: next(plans)):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "repair_update_exception")
        self.assertEqual(call.await_count, 5)

    async def test_verification_read_exception_is_fail_closed(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, RuntimeError("verification transport lost")])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "post_repair_verification_exception")
        self.assertEqual(call.await_count, 4)

    async def test_verification_read_tool_error_is_fail_closed(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, {"isError": True, "content": [{"type": "text", "text": "verification rejected"}]}])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "post_repair_verification_tool_error")
        self.assertEqual(call.await_count, 4)

    async def test_unchanged_workflow_after_update_fails_verification(self):
        workflow = {"nodes": [{"name": "stable"}], "connections": {}, "active": False}
        plan = {"ok": True, "operations": [{"type": "removeConnection"}], "remaining_issues": []}
        call = AsyncMock(side_effect=[workflow, workflow, {"ok": True}, workflow])
        logger = Mock()
        with patch.object(gate, "_enabled", return_value=True), patch.object(gate, "configured", return_value=True), patch.object(gate, "decision", return_value=(True, "ok")), patch.object(gate, "call_tool", call), patch.object(gate, "_payload", side_effect=lambda x: x), patch.object(gate, "_workflow_fingerprint", return_value="stable-fingerprint"), patch.object(gate, "plan_safe_ecom_repair", return_value=plan):
            result = await gate.maybe_apply_safe_ecom_repair(logger)
        self.assertFalse(result["ok"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "workflow_unchanged_after_repair")
        self.assertEqual(call.await_count, 4)


if __name__ == "__main__":
    unittest.main()
