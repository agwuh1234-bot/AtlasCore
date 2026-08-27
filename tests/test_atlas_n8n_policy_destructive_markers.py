import os
import unittest
from unittest.mock import patch

from atlas_n8n_policy import classify_tool, decision


class N8NPolicyDestructiveMarkerTests(unittest.TestCase):
    def test_reset_clear_revoke_terminate_cancel_are_destructive(self):
        for name in (
            "reset_workflow",
            "clear_execution_history",
            "revoke_credential",
            "terminate_execution",
            "cancel_run",
        ):
            with self.subTest(name=name):
                self.assertEqual("destructive", classify_tool(name))

    def test_new_destructive_markers_require_separate_opt_in(self):
        with patch.dict(os.environ, {"N8N_WRITES_ENABLED": "true", "N8N_DESTRUCTIVE_ENABLED": ""}, clear=False):
            allowed, reason = decision("reset_workflow", "write")
        self.assertFalse(allowed)
        self.assertEqual("destructive_disabled", reason)


if __name__ == "__main__":
    unittest.main()
