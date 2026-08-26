import unittest

import atlas_n8n_ecom_run as run_gate


class FailedExecutionReceiptTests(unittest.TestCase):
    def test_failed_status_overrides_execution_id(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "failed"})
        self.assertFalse(receipt["confirmed"])
        self.assertTrue(receipt["execution_id_present"])
        self.assertEqual(receipt["status"], "failed")

    def test_error_status_overrides_execution_id(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "error"})
        self.assertFalse(receipt["confirmed"])

    def test_cancelled_status_overrides_execution_id(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "cancelled"})
        self.assertFalse(receipt["confirmed"])

    def test_unknown_explicit_status_fails_closed_even_with_execution_id(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "timed_out"})
        self.assertFalse(receipt["confirmed"])
        self.assertTrue(receipt["execution_id_present"])
        self.assertEqual(receipt["status"], "timed_out")

    def test_execution_id_without_status_remains_confirmed(self):
        receipt = run_gate._execution_receipt({"executionId": "123"})
        self.assertTrue(receipt["confirmed"])

    def test_success_status_with_execution_id_remains_confirmed(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "success"})
        self.assertTrue(receipt["confirmed"])

    def test_matching_workflow_id_is_confirmed(self):
        receipt = run_gate._execution_receipt(
            {"executionId": "123", "status": "success", "workflowId": run_gate.TARGET_WORKFLOW_ID}
        )
        self.assertTrue(receipt["confirmed"])
        self.assertTrue(receipt["workflow_id_present"])
        self.assertTrue(receipt["workflow_id_matches"])

    def test_mismatched_workflow_id_fails_closed_even_on_success(self):
        receipt = run_gate._execution_receipt(
            {"executionId": "123", "status": "success", "workflowId": "other-workflow"}
        )
        self.assertFalse(receipt["confirmed"])
        self.assertTrue(receipt["workflow_id_present"])
        self.assertFalse(receipt["workflow_id_matches"])

    def test_container_execution_id_is_rejected(self):
        receipt = run_gate._execution_receipt({"executionId": {"id": "123"}})
        self.assertFalse(receipt["confirmed"])
        self.assertFalse(receipt["execution_id_present"])

    def test_boolean_execution_id_is_rejected(self):
        receipt = run_gate._execution_receipt({"executionId": True})
        self.assertFalse(receipt["confirmed"])
        self.assertFalse(receipt["execution_id_present"])

    def test_container_workflow_id_fails_closed_even_on_success(self):
        receipt = run_gate._execution_receipt(
            {"executionId": "123", "status": "success", "workflowId": {"id": run_gate.TARGET_WORKFLOW_ID}}
        )
        self.assertFalse(receipt["confirmed"])
        self.assertTrue(receipt["workflow_id_present"])
        self.assertFalse(receipt["workflow_id_matches"])

    def test_oversized_execution_id_is_rejected(self):
        receipt = run_gate._execution_receipt({"executionId": "x" * 257})
        self.assertFalse(receipt["confirmed"])
        self.assertFalse(receipt["execution_id_present"])


if __name__ == "__main__":
    unittest.main()
