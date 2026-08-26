import unittest

from atlas_n8n_ecom import _workflow_safety_summary
from atlas_n8n_ecom_repair import plan_safe_ecom_repair


class LiveEcomWorkflowSnapshotTests(unittest.TestCase):
    def _live_snapshot(self):
        return {
            "id": "0S8720gc3G2OODmG",
            "name": "ecomSX222",
            "active": False,
            "nodes": [
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": True},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
                {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True},
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
                {"name": "Sticky Note", "type": "n8n-nodes-base.stickyNote", "disabled": False},
            ],
            "connections": {
                "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
                "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]},
                "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
                "Message a model": {"main": [[{"node": "Edit a file", "type": "main", "index": 0}]]},
            },
        }

    def test_current_live_snapshot_is_blocked_for_manual_run(self):
        safety = _workflow_safety_summary(self._live_snapshot())
        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertEqual(
            safety["issues"],
            [
                "unsafe_connection:Message a model->Edit a file",
                "unexpected_reachable_node:Edit a file",
            ],
        )

    def test_current_live_snapshot_has_one_narrow_deterministic_repair(self):
        plan = plan_safe_ecom_repair(self._live_snapshot())
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["remaining_issues"], [])
        self.assertEqual(
            plan["operations"],
            [
                {
                    "type": "removeConnection",
                    "source": "Message a model",
                    "target": "Edit a file",
                    "ignoreErrors": False,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
