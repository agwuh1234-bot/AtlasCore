from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class N8NSafetyIntegrityTests(unittest.TestCase):
    def test_bridge_keeps_write_and_destructive_gates(self):
        text = (ROOT / "atlas_n8n.py").read_text(encoding="utf-8")
        self.assertIn("N8N_WRITES_ENABLED", text)
        self.assertIn("N8N_DESTRUCTIVE_ENABLED", text)
        self.assertIn("removeConnection", text)

    def test_policy_remains_fail_closed_for_unknown_tools(self):
        text = (ROOT / "atlas_n8n_policy.py").read_text(encoding="utf-8")
        self.assertIn("unknown", text.lower())
        self.assertIn("write", text.lower())
        self.assertIn("destructive", text.lower())

    def test_ecom_workflow_keeps_legacy_write_nodes_disabled(self):
        text = (ROOT / "atlas_n8n_ecom.py").read_text(encoding="utf-8")
        for node in ("HTTP Request", "HTTP Request1", "Edit a file"):
            self.assertIn(node, text)
        self.assertIn("ready_for_safe_manual_run", text)
        self.assertIn("unsafe_node_enabled", text)
        self.assertIn("unexpected_reachable_node", text)

    def test_manual_run_gate_keeps_double_check_and_fingerprint(self):
        text = (ROOT / "atlas_n8n_ecom_run.py").read_text(encoding="utf-8")
        self.assertIn("fingerprint", text.lower())
        self.assertIn("ready_for_safe_manual_run", text)
        self.assertIn("active", text.lower())


if __name__ == "__main__":
    unittest.main()
