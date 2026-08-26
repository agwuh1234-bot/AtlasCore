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

    def test_success_status_with_execution_id_remains_confirmed(self):
        receipt = run_gate._execution_receipt({"executionId": "123", "status": "success"})
        self.assertTrue(receipt["confirmed"])


if __name__ == "__main__":
    unittest.main()
