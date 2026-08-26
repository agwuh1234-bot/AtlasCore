from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class N8NSafetyIntegrityTests(unittest.TestCase):
    def test_bridge_keeps_write_and_destructive_gates(self):
        bridge = (ROOT / "atlas_n8n.py").read_text(encoding="utf-8")
        policy = (ROOT / "atlas_n8n_policy.py").read_text(encoding="utf-8")

        # Ordinary writes are centrally gated by policy; destructive nested
        # workflow operations still require the separate destructive opt-in.
        self.assertIn("decision(tool_name, intent)", bridge)
        self.assertIn("N8N_DESTRUCTIVE_ENABLED", bridge)
        self.assertIn("_contains_destructive_workflow_operation", bridge)
        self.assertIn("write_disabled", policy)

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
        self.assertIn("_workflow_fingerprint", text)
        self.assertGreaterEqual(text.count("get_workflow_details"), 2)
        self.assertIn("execution_readiness", text)
        self.assertIn("workflow_active", text)
        self.assertIn("workflow_changed_during_preflight", text)


if __name__ == "__main__":
    unittest.main()
